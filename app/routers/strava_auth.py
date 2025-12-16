import os
import httpx
from fastapi import APIRouter, Depends, Query, Request, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from .. import models
from ..dependencies import get_db, create_access_token

router = APIRouter(prefix="/auth/strava", tags=["auth"])

STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET")
# Default to local dev URL, should be env var in prod
STRAVA_REDIRECT_URI = os.getenv("STRAVA_REDIRECT_URI", "http://localhost:8000/auth/strava/callback")

@router.get("/login")
def strava_login():
    if not STRAVA_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Strava Client ID not configured")
        
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
        token_resp = await client.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            }
        )
        
    if token_resp.status_code != 200:
         return RedirectResponse(url="/login?error=TokenExchangeFailed", status_code=status.HTTP_303_SEE_OTHER)
         
    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_at = token_data.get("expires_at") # Timestamp
    athlete = token_data.get("athlete", {})
    
    strava_id = str(athlete.get("id"))
    username = athlete.get("username")
    # Strava doesn't guarantee username presence, so we fallback
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
        # Update connection expiration if needed
        db.commit()
    else:
        # No connection -> Check if user exists by email (if email is trusted? Strava doesn't always send email)
        # Strava often doesn't send email unless scoped. current scope has no email.
        # So we treat as new user or ask to link?
        # For simplicity MVP: Create new user if not exists based on deduced username
        
        # Check username collision
        base_username = username
        counter = 1
        while db.query(models.User).filter(models.User.username == username).first():
             username = f"{base_username}{counter}"
             counter += 1
             
        # Create User
        user = models.User(
            username=username,
            email=None, # Strava doesn't provide email easily without scope, make nullable or placeholder?
            hashed_password=None, # No password for OAuth users
            full_name=f"{athlete.get('firstname')} {athlete.get('lastname')}",
            profile_picture=athlete.get("profile"),
            location_city=athlete.get("city"),
            location_country=athlete.get("country"),
            strava_url=f"https://www.strava.com/athletes/{strava_id}",
            role=models.Role.USER
        )
        db.add(user)
        db.commit() # Commit to get ID
        
        # Create Connection
        new_conn = models.OAuthConnection(
            user_id=user.id,
            provider=models.OAuthProvider.STRAVA,
            provider_user_id=strava_id,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        db.add(new_conn)
        db.commit()

    # 3. Create Session
    access_token_jwt = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/explore", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {access_token_jwt}", 
        httponly=True,
        max_age=60 * 60 * 24 * 30, # 30 days
        expires=60 * 60 * 24 * 30
    )
    
    return response
