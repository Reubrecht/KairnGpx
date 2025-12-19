import os
import httpx
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request, status, HTTPException, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from .. import models, utils
from ..services.analytics import GpxAnalytics
from ..services.ai_analyzer import AiAnalyzer
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

# --- Activity Import Features ---

def convert_streams_to_gpx(activity_data: dict, streams: list) -> bytes:
    """
    Convert Strava Streams into a GPX file.
    """
    # 1. Parse Streams
    latlng = []
    altitude = []
    times = []
    heartrate = []
    
    # Streams is a list of dicts: [{"type": "latlng", "data": [...]}, ...]
    # Strava API returns wrapper if key_by_type=true is NOT used, but we will use key_by_type=true
    # Actually client.get params are cleaner if we assume list response or dict response.
    # Let's handle list response which is default for streams endpoint
    
    data_len = 0
    
    # We will request with key_by_type=true for easier parsing
    # Response structure: { "latlng": { "data": [...] }, "time": { "data": [...] } }
    
    if isinstance(streams, list): 
        # Convert list format to dict for easier access if API returns list
        streams_dict = {s["type"]: s for s in streams}
    else:
        streams_dict = streams
        
    if "latlng" in streams_dict:
        latlng = streams_dict["latlng"]["data"]
        data_len = len(latlng)
    
    if "altitude" in streams_dict:
        altitude = streams_dict["altitude"]["data"]
        
    if "time" in streams_dict:
        times = streams_dict["time"]["data"]
        
    if "heartrate" in streams_dict:
        heartrate = streams_dict["heartrate"]["data"]
        
    if data_len == 0:
        return b""

    # 2. Build GPX String
    # Simple string build is faster/lighter than full XML lib for this specific structure
    gpx_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Kairn Strava Import" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">',
        ' <metadata>',
        f'  <name>{activity_data.get("name", "Strava Activity")}</name>',
        f'  <time>{activity_data.get("start_date")}</time>',
        ' </metadata>',
        ' <trk>',
        f'  <name>{activity_data.get("name", "Activity")}</name>',
        '  <trkseg>'
    ]
    
    start_time_str = activity_data.get("start_date") # ISO 8601 e.g. 2018-02-16T14:52:54Z
    # We need strictly formatted timestamps for points if we want to be exact,
    # but strictly speaking GPX <time> in trkpt is optional, though good for stats.
    # The 'time' stream is seconds relative to start.
    
    try:
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%SZ")
    except:
        start_dt = datetime.utcnow() # Fallback

    for i in range(data_len):
        lat, lon = latlng[i]
        ele = altitude[i] if i < len(altitude) else 0
        
        # Time calc
        if i < len(times):
            offset = times[i]
            # Simple add (ignoring leap seconds etc)
            import datetime as dt_mod # avoid conflict
            pt_time = (start_dt + dt_mod.timedelta(seconds=int(offset))).isoformat() + "Z"
            time_tag = f"<time>{pt_time}</time>"
        else:
            time_tag = ""
            
        # HR ext
        ext_tag = ""
        if i < len(heartrate):
             ext_tag = f"<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{heartrate[i]}</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions>"

        gpx_lines.append(f'   <trkpt lat="{lat}" lon="{lon}">')
        gpx_lines.append(f'    <ele>{ele}</ele>')
        if time_tag: gpx_lines.append(f'    {time_tag}')
        if ext_tag: gpx_lines.append(f'    {ext_tag}')
        gpx_lines.append('   </trkpt>')
        
    gpx_lines.append('  </trkseg>')
    gpx_lines.append(' </trk>')
    gpx_lines.append('</gpx>')
    
    return "\n".join(gpx_lines).encode("utf-8")


@router.get("/activities")
async def list_strava_activities(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """List activities from the authenticated user's Strava account"""
    try:
        token = await get_valid_token(current_user.id, db)
    except HTTPException as e:
        raise e
    except Exception as e:
         print(f"Error getting Strava token: {e}")
         raise HTTPException(status_code=400, detail="Could not connect to Strava")

    conn = db.query(models.OAuthConnection).filter(
        models.OAuthConnection.user_id == current_user.id,
        models.OAuthConnection.provider == models.OAuthProvider.STRAVA
    ).first()
    
    async with httpx.AsyncClient() as client:
        # Get Activities
        url = "https://www.strava.com/api/v3/athlete/activities"
        
        resp = await client.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": 30} # Last 30 activities
        )
        
        if resp.status_code == 401:
            raise HTTPException(status_code=401, detail="Strava session invalid. Please reconnect.")

    if resp.status_code != 200:
        print(f"ERROR: Strava Activity List Failed: {resp.text}")
        raise HTTPException(status_code=resp.status_code, detail=f"Strava API error: {resp.text}")
        
    return resp.json()

@router.post("/activities/{activity_id}/import")
async def import_strava_activity(
    activity_id: str, 
    # Form fields from unified UI (optional, defaults to Strava data if missing)
    title: str = Form(None),
    description: str = Form(None),
    activity_type: str = Form(None),
    visibility: str = Form(None),
    tags: str = Form(None), # Comma separated
    environment: list[str] = Form(None),
    scenery_rating: int = Form(None),
    water_points_count: int = Form(None),
    # Race details
    is_official_bot: bool = Form(None),
    race_name: str = Form(None),
    race_year: int = Form(None),
    race_route_name: str = Form(None),
    
    db: Session = Depends(get_db), 
    current_user = Depends(get_current_user)
):
    """Import a specific Strava Activity as a Kairn Track"""
    
    token = await get_valid_token(current_user.id, db)

    # 1. Fetch Activity Details
    async with httpx.AsyncClient() as client:
        detail_resp = await client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
             headers={"Authorization": f"Bearer {token}"}
        )
    
    if detail_resp.status_code != 200:
        raise HTTPException(status_code=detail_resp.status_code, detail="Could not fetch activity details")
        
    activity_details = detail_resp.json()
    
    # 2. Fetch Streams (LatLng, Alt, Time)
    # key_by_type=true returns a dict {latlng:.., altitude:..}
    async with httpx.AsyncClient() as client:
        streams_resp = await client.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "keys": "latlng,altitude,time,heartrate",
                "key_by_type": "true" 
            }
        )
        
    if streams_resp.status_code != 200:
         # Some manual activities might not have streams
         raise HTTPException(status_code=400, detail="This activity has no GPS data to import")
         
    streams = streams_resp.json()
    
    # Extract Coordinates for Map & Location
    start_lat, start_lon = None, None
    end_lat, end_lon = None, None
    
    # Strava returns streams as a list of dicts if key_by_type=false, BUT key_by_type=true gives a dict.
    # We used key_by_type=true.
    # streams structure: { "latlng": {"data": [[lat, lon], ...]}, ... }
    
    if "latlng" in streams and "data" in streams["latlng"] and len(streams["latlng"]["data"]) > 0:
        coords_data = streams["latlng"]["data"]
        start_lat, start_lon = coords_data[0]
        end_lat, end_lon = coords_data[-1]
        
    # Geocode Location
    city, region, country = None, None, None
    if start_lat and start_lon:
        city, region, country = utils.get_location_info(start_lat, start_lon)

    
    # 3. Convert to GPX
    gpx_content = convert_streams_to_gpx(activity_details, streams)
    
    if not gpx_content:
        raise HTTPException(status_code=400, detail="Could not generate GPX (Empty track?)")

    # --- ANALYTICS INTEGRATION ---
    # Calculate detailed metrics using our internal service
    analytics = GpxAnalytics(gpx_content)
    metrics = analytics.calculate_metrics()
    
    if not metrics:
         raise HTTPException(status_code=400, detail="Could not analyze generated GPX")
         
    # 4. Save & Create Track

    # Determine Base Metadata (User input > Strava Default)
    final_title = title if title else activity_details.get("name", f"Strava Activity {activity_id}")
    final_description = description if description else activity_details.get("description", "")
    
    inferred_tags = []
    
    # Process User Tags
    user_tags = []
    if tags:
        user_tags = [t.strip() for t in tags.split(",") if t.strip()]
    
    # --- AI ANALYSIS ---
    try:
        ai_analyzer = AiAnalyzer()
        if ai_analyzer.model:
            print(f"Calling Gemini for Strava Activity {activity_id}...")
            
            gpx_meta = analytics.get_metadata() 
            
            ai_data = ai_analyzer.analyze_track(
                metrics, 
                metadata=gpx_meta, 
                user_title=final_title, 
                user_description=final_description,
                is_race=is_official_bot or False 
            )
            
            # If user provided a custom description, we append AI info or keep user's authoritative?
            # Usually users appreciate AI enhancement. But if they wrote a specific text, they want it kept.
            # Strategy: If User wrote description > Use User Description + AI summary appended maybe? 
            # Or just let AI generate and user can edit later.
            # BUT user asked to edit BEFORE. So user input is high signal.
            # If user provided input, using it as `user_description` for AI prompts it effectively.
            # The AI returns a generated description. 
            
            if ai_data.get("ai_description"):
                final_description = ai_data["ai_description"] # AI usually writes better based on input
            
            if ai_data.get("ai_title"):
                final_title = ai_data["ai_title"]
                
            if ai_data.get("ai_tags"):
                inferred_tags.extend(ai_data["ai_tags"])
                
    except Exception as e:
        print(f"AI Analysis (Strava) failed: {e}")
        
    # Merge Tags
    all_tags = list(set(user_tags + inferred_tags))
    
    # Save GPX
    filename = f"strava_activity_{activity_id}.gpx"
    save_path = f"app/uploads/{filename}"
    os.makedirs("app/uploads", exist_ok=True)
    
    with open(save_path, "wb") as f:
        f.write(gpx_content)
        
    file_hash = utils.calculate_file_hash(gpx_content)
    
    existing = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
    if existing:
        return {"id": existing.id, "status": "duplicate", "message": "Track already exists"}
        
    new_track = models.Track(
        title=final_title,
        description=final_description,
        user_id=current_user.id,
        uploader_name=current_user.username,
        source_type=models.SourceType.STRAVA_IMPORT,
        file_path=f"app/uploads/{filename}",
        file_hash=file_hash,
        visibility=models.Visibility(visibility) if visibility else models.Visibility.PRIVATE,
        
        # Location & Coords
        start_lat = start_lat,
        start_lon = start_lon,
        end_lat = end_lat,
        end_lon = end_lon,
        location_city = city,
        location_region = region,
        location_country = country, 
        
        # Detailed Metrics from Analytics
        distance_km = metrics["distance_km"],
        elevation_gain = metrics["elevation_gain"],
        elevation_loss = metrics["elevation_loss"],
        max_altitude = metrics["max_altitude"],
        min_altitude = metrics["min_altitude"],
        avg_altitude = metrics["avg_altitude"],
        
        max_slope = metrics["max_slope"],
        avg_slope_uphill = metrics["avg_slope_uphill"],
        
        km_effort = metrics["km_effort"],
        itra_points_estim = metrics["itra_points_estim"],
        ibp_index = metrics.get("ibp_index"),
        longest_climb = metrics.get("longest_climb"),
        
        route_type = metrics["route_type"],
        estimated_times = metrics["estimated_times"],
        
        tags = all_tags,
        
        # Environments & Extras from Form
        environment = environment,
        scenery_rating = scenery_rating,
        water_points_count = water_points_count,
        
        # Race Info
        is_official_route = is_official_bot,
        # race_name, race_year, race_route_name need separate handling (RaceRoute creation)
        # For now, excluding them to prevent TypeError as Track model doesn't have these fields.
    )

    
    # Fallback: If Strava has "official" distance/elevation that differs significantly, 
    # we might want to trust Strava? 
    # For now, let's trust our analysis of the raw stream data for consistency with slopes/profiles.
    # Strava's `total_elevation_gain` is often corrected on their side, while our `metrics` is raw from points.
    # However, user feedback usually prefers "what they see on Strava".
    # BUT, our `km_effort` depends on `elevation_gain` we have.
    # Let's stick to OUR metrics for consistency between the number displayed and the Profile Chart.

    
    # Strava Type Mapping
    strava_type = activity_details.get("type")
    # Simple mapping
    type_map = {
        "Run": models.ActivityType.RUNNING,
        "TrailRun": models.ActivityType.TRAIL_RUNNING,
        "Hike": models.ActivityType.HIKING,
        "Ride": models.ActivityType.ROAD_CYCLING,
        "GravelRide": models.ActivityType.GRAVEL,
        "MountainBikeRide": models.ActivityType.MTB_CROSS_COUNTRY,
        "AlpineSki": models.ActivityType.SKI_TOURING, # Approx
        "BackcountrySki": models.ActivityType.SKI_TOURING
    }
    if strava_type in type_map:
        new_track.activity_type = type_map[strava_type]
    
    db.add(new_track)
    db.commit()
    db.refresh(new_track)
    
    return {"id": new_track.id, "status": "imported", "title": new_track.title}
