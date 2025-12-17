import os
import httpx
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request, status, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from .. import models, utils
from ..dependencies import get_db, create_access_token, get_current_user

router = APIRouter(prefix="/auth/strava", tags=["auth"])

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
# Default to local dev URL, should be env var in prod
STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI", "http://localhost:8000/auth/strava/callback")

# --- Helper: Token Management ---

async def get_valid_token(user_id: int, db: Session) -> str:
    """
    Retrieves a valid access token for the given user. 
    Refreshes the token if it is expired or close to expiration (< 5 mins).
    """
    connection = db.query(models.OAuthConnection).filter(
        models.OAuthConnection.user_id == user_id,
        models.OAuthConnection.provider == models.OAuthProvider.STRAVA
    ).first()

    if not connection:
        raise HTTPException(status_code=400, detail="Strava not connected")

    # Check expiration
    now = datetime.utcnow()
    # Buffer: 5 minutes
    is_expired = False
    
    if connection.expires_at:
        # Calculate time remaining (total_seconds)
        time_remaining = (connection.expires_at - now).total_seconds()
        if time_remaining < 300: # Less than 5 mins
            is_expired = True
    else:
        # If no expiration date known, force refresh to be safe.
        is_expired = True

    if not is_expired:
        return connection.access_token

    # Refresh functionality
    print(f"DEBUG: Refreshing Strava Token for User {connection.user_id}")
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": connection.refresh_token
            }
        )
        
    if resp.status_code != 200:
        print(f"ERROR: Strava Refresh Failed: {resp.text}")
        raise HTTPException(status_code=401, detail="Strava Connection Expired. Please reconnect.")
        
    data = resp.json()
    new_access_token = data.get("access_token")
    new_refresh_token = data.get("refresh_token")
    new_expires_at_ts = data.get("expires_at") # Timestamp
    
    # Update DB
    connection.access_token = new_access_token
    connection.refresh_token = new_refresh_token
    if new_expires_at_ts:
        connection.expires_at = datetime.fromtimestamp(new_expires_at_ts)
        
    db.commit()
    
    return new_access_token

# --- Auth Routes ---

@router.get("/login")
def strava_login():
    if not STRAVA_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Strava Client ID not configured")
        
    # Scopes: 
    # read: Basic read
    # activity:read_all: Read all activities (required for import)
    # profile:read_all: Read profile (required for bio/weight/etc if private)
    scope = "read,profile:read_all,activity:read_all" 
    
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={STRAVA_REDIRECT_URI}"
        f"&approval_prompt=auto"
        f"&scope={scope}"
    )
    return RedirectResponse(url)

@router.get("/callback")
async def strava_callback(request: Request, code: str = Query(None), error: str = Query(None), db: Session = Depends(get_db)):
    if error:
        return RedirectResponse(url=f"/login?error=StravaAuthFailed_{error}", status_code=status.HTTP_303_SEE_OTHER)
    
    if not code:
        return RedirectResponse(url="/login?error=NoCodeProvided", status_code=status.HTTP_303_SEE_OTHER)

    # 1. Exchange code for token
    async with httpx.AsyncClient() as client:
        # Debug: Print what we are sending
        print(f"DEBUG: Exchanging code for token. ClientID={STRAVA_CLIENT_ID}")
        
        token_resp = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": STRAVA_REDIRECT_URI, 
            }
        )
        
    if token_resp.status_code != 200:
         print(f"ERROR: Strava Token Exchange Failed: {token_resp.status_code} - {token_resp.text}")
         return RedirectResponse(url=f"/login?error=TokenExchangeFailed_{token_resp.status_code}", status_code=status.HTTP_303_SEE_OTHER)
         
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_at_ts = token_data.get("expires_at") # Timestamp integer
    expires_at_dt = datetime.fromtimestamp(expires_at_ts) if expires_at_ts else None

    athlete = token_data.get("athlete", {})
    
    strava_id = str(athlete.get("id"))
    username = athlete.get("username")
    
    # Strava doesn't guarantee username
    if not username:
        username = f"{athlete.get('firstname', 'User')}{athlete.get('lastname', '')}".replace(" ", "").lower()
        
    # 2. Check if user exists via OAuthConnection
    connection = db.query(models.OAuthConnection).filter(
        models.OAuthConnection.provider == models.OAuthProvider.STRAVA,
        models.OAuthConnection.provider_user_id == strava_id
    ).first()
    
    user = None
    
    if connection:
        # Existing connection -> Log them in
        user = connection.user
        # Update tokens
        connection.access_token = access_token
        connection.refresh_token = refresh_token
        connection.expires_at = expires_at_dt
        db.commit()
    else:
        # No connection -> Check if user exists by email (MERGING)
        strava_email = athlete.get('email') 
        
        if strava_email:
             existing_user = db.query(models.User).filter(models.User.email == strava_email).first()
             if existing_user:
                 print(f"DEBUG: Merging Strava account {strava_id} with existing user {existing_user.username}")
                 user = existing_user
                 # Create Connection linked to this user
                 new_conn = models.OAuthConnection(
                    user_id=user.id,
                    provider=models.OAuthProvider.STRAVA,
                    provider_user_id=strava_id,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at_dt
                 )
                 db.add(new_conn)
                 db.commit()
        
        if not user:
            # Create New User
            
            # Check username collision
            base_username = username
            counter = 1
            while db.query(models.User).filter(models.User.username == username).first():
                 username = f"{base_username}{counter}"
                 counter += 1
                 
            user = models.User(
                username=username,
                email=strava_email, # Might be None
                hashed_password=None,
                role=models.Role.USER
            )
            db.add(user)
            db.commit()
            
            # Create Connection
            new_conn = models.OAuthConnection(
                user_id=user.id,
                provider=models.OAuthProvider.STRAVA,
                provider_user_id=strava_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at_dt
            )
            db.add(new_conn)
            db.commit()

    # 3. Sync Profile Data
    
    # Name
    if athlete.get('firstname') and athlete.get('lastname'):
        user.full_name = f"{athlete.get('firstname')} {athlete.get('lastname')}"
    
    # Images
    if athlete.get("profile"):
        user.profile_picture = athlete.get("profile")
    if athlete.get("profile_medium"):
         user.profile_picture = athlete.get("profile_medium")
         
    # Bio
    if athlete.get("bio"):
        user.bio = athlete.get("bio")
        
    # Physio
    if athlete.get("weight"):
        user.weight = athlete.get("weight") # kg
    
    # Gender
    start_gender = athlete.get("sex")
    if start_gender == "M":
        user.gender = "Male"
    elif start_gender == "F":
        user.gender = "Female"
        
    # Location
    city = athlete.get("city")
    region = athlete.get("state")
    country = athlete.get("country")
    
    user.location_city = city
    user.location_region = region
    user.location_country = country
    
    # Construct location string
    loc_parts = [p for p in [city, country] if p]
    if loc_parts:
        qs = ", ".join(loc_parts)
        user.location = qs 
        
        # Geocode if lat/lon missing
        lat, lon = utils.geocode_location(qs)
        if lat and lon:
            user.location_lat = lat
            user.location_lon = lon
            
    # Links
    user.strava_url = f"https://www.strava.com/athletes/{strava_id}"
    
    db.commit()

    # 4. Create Session
    access_token_jwt = create_access_token(data={"sub": user.username})
    
    redirect_dest = "/explore"
        
    response = RedirectResponse(url=redirect_dest, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token_jwt}", 
        httponly=True,
        max_age=60 * 60 * 24 * 30, # 30 days
        expires=60 * 60 * 24 * 30
    )
    
    return response

# --- Route Import Features ---

@router.get("/routes")
async def list_strava_routes(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """List routes from the authenticated user's Strava account"""
    # Use helper to get valid token
    try:
        token = await get_valid_token(current_user.id, db)
    except HTTPException as e:
        raise e
    except Exception as e:
         print(f"Error getting Strava token: {e}")
         raise HTTPException(status_code=400, detail="Could not connect to Strava")

    # Get Strava connection for athlete_id
    conn = db.query(models.OAuthConnection).filter(
        models.OAuthConnection.user_id == current_user.id,
        models.OAuthConnection.provider == models.OAuthProvider.STRAVA
    ).first()
    
    async with httpx.AsyncClient() as client:
        # Get routes
        url = f"https://www.strava.com/api/v3/athletes/{conn.provider_user_id}/routes"
        
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": 50}
        )
        
        # If 401 despite check, likely revoked
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Strava session invalid. Please reconnect.")

    if resp.status_code != 200:
        print(f"ERROR: Strava Route List Failed: {resp.text}")
        raise HTTPException(status_code=resp.status_code, detail=f"Strava API error: {resp.text}")
        
    return resp.json()

@router.post("/routes/{route_id}/import")
async def import_strava_route(route_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """Import a specific Strava route as a Kairn Track"""
    
    token = await get_valid_token(current_user.id, db)

    # 1. Fetch Route GPX
    async with httpx.AsyncClient() as client:
        export_url = f"https://www.strava.com/api/v3/routes/{route_id}/export_gpx"
        
        resp = await client.get(
            export_url,
            headers={"Authorization": f"Bearer {token}"},
            follow_redirects=True
        )
        
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="Could not fetch GPX from Strava")
            
    gpx_content = resp.content
    
    # 2. Get details
    async with httpx.AsyncClient() as client:
        detail_resp = await client.get(
            f"https://www.strava.com/api/v3/routes/{route_id}",
             headers={"Authorization": f"Bearer {token}"}
        )
    
    route_details = detail_resp.json() if detail_resp.status_code == 200 else {}
    
    title = route_details.get("name", f"Strava Import {route_id}")
    description = route_details.get("description", "")
    
    # Save GPX
    filename = f"strava_{route_id}.gpx"
    save_path = f"app/uploads/{filename}"
    os.makedirs("app/uploads", exist_ok=True)
    
    with open(save_path, "wb") as f:
        f.write(gpx_content)
        
    file_hash = utils.calculate_file_hash(gpx_content)
    
    existing = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
    if existing:
        return {"id": existing.id, "status": "duplicate", "message": "Track already exists"}
        
    new_track = models.Track(
        title=title,
        description=description,
        user_id=current_user.id,
        uploader_name=current_user.username,
        source_type=models.SourceType.STRAVA_IMPORT,
        file_path=f"app/uploads/{filename}",
        file_hash=file_hash,
        visibility=models.Visibility.PRIVATE # Default private
    )
    
    # Metrics
    new_track.distance_km = route_details.get("distance", 0) / 1000.0
    new_track.elevation_gain = route_details.get("elevation_gain", 0)
    
    db.add(new_track)
    db.commit()
    db.refresh(new_track)
    
    return {"id": new_track.id, "status": "imported", "title": new_track.title}
