import os
import httpx
from datetime import datetime
from fastapi import APIRouter, Request, status, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from .. import models, utils
from ..dependencies import get_db
from ..database import SessionLocal
from ..services.analytics import GpxAnalytics
from ..services.ai_analyzer import AiAnalyzer
from .strava_auth import get_valid_token, convert_streams_to_gpx

router = APIRouter(prefix="/webhooks/strava", tags=["webhooks"])

VERIFY_TOKEN = os.getenv("STRAVA_VERIFY_TOKEN", "STRAVA")

@router.get("")
def verify_webhook(request: Request):
    """
    Strava Webhook Verification.
    Responds to the challenge from Strava to confirm ownership.
    """
    params = request.query_params
    hub_mode = params.get("hub.mode")
    hub_challenge = params.get("hub.challenge")
    hub_verify_token = params.get("hub.verify_token")

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("WEBHOOK_VERIFIED")
        return {"hub.challenge": hub_challenge}
    
    raise HTTPException(status_code=403, detail="Invalid verify token")

@router.post("")
async def webhook_event(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Receive Strava Events.
    """
    payload = await request.json()
    print(f"WEBHOOK_RECEIVED: {payload}")
    
    object_type = payload.get("object_type") # 'activity' or 'athlete'
    aspect_type = payload.get("aspect_type") # 'create', 'update', 'delete'
    object_id = payload.get("object_id")
    owner_id = payload.get("owner_id") # Strava Athlete ID
    updates = payload.get("updates", {})
    
    # Process asynchronously to avoid blocking webhook response
    if object_type == "activity" and aspect_type == "create":
        background_tasks.add_task(process_new_activity, object_id, owner_id)
    elif object_type == "athlete" and aspect_type == "update":
         background_tasks.add_task(process_athlete_update, owner_id, updates)
         
    return {"status": "ok"}

async def process_new_activity(activity_id: int, strava_athlete_id: int):
    """
    Fetch and import new activity from Strava.
    MODIFIED: Now stores only summary stats in StravaActivity model.
    Does NOT create a GPX Track file.
    """
    print(f"Processing new activity {activity_id} for athlete {strava_athlete_id}")

    db = SessionLocal()
    try:
        # 1. Find User via OAuthConnection
        connection = db.query(models.OAuthConnection).filter(
            models.OAuthConnection.provider == models.OAuthProvider.STRAVA,
            models.OAuthConnection.provider_user_id == str(strava_athlete_id)
        ).first()

        if not connection:
            print(f"Skipping activity {activity_id}: User not found for Strava ID {strava_athlete_id}")
            return

        user = connection.user

        # 2. Get Valid Token
        try:
            token = await get_valid_token(user.id, db)
        except Exception as e:
            print(f"Error getting token for user {user.username}: {e}")
            return

        # 3. Fetch Activity Details
        async with httpx.AsyncClient() as client:
            detail_resp = await client.get(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers={"Authorization": f"Bearer {token}"}
            )

        if detail_resp.status_code != 200:
            print(f"Error fetching activity {activity_id}: {detail_resp.status_code}")
            return

        activity_details = detail_resp.json()

        # 4. Check for duplicates
        existing = db.query(models.StravaActivity).filter(models.StravaActivity.strava_id == str(activity_id)).first()
        if existing:
             print(f"Activity {activity_id} already exists in Club Stats.")
             return

        # 5. Extract Stats
        # Strava returns: distance (meters), moving_time (seconds), elapsed_time (seconds), total_elevation_gain (meters), type, start_date (ISO)
        
        start_date_str = activity_details.get("start_date")
        try:
            start_date_dt = datetime.strptime(start_date_str, "%Y-%m-%dT%H:%M:%SZ")
        except:
            start_date_dt = datetime.utcnow()

        new_activity = models.StravaActivity(
            user_id=user.id,
            strava_id=str(activity_id),
            name=activity_details.get("name", "Strava Activity"),
            distance=activity_details.get("distance", 0.0),
            moving_time=activity_details.get("moving_time", 0),
            elapsed_time=activity_details.get("elapsed_time", 0),
            total_elevation_gain=activity_details.get("total_elevation_gain", 0.0),
            type=activity_details.get("type", "Unknown"),
            start_date=start_date_dt
        )
        
        db.add(new_activity)
        db.commit()
        print(f"Successfully saved Strava Activity Stats {activity_id} for User {user.username}")

        # NOTE: WE DO NOT DOWNLOAD STREAMS OR CREATE TRACKS ANYMORE as per requirement.
        
    except Exception as e:
        print(f"Error processing activity {activity_id}: {e}")
        db.rollback()
    finally:
        db.close()

async def process_athlete_update(strava_athlete_id: int, updates: dict):
    print(f"Processing update for athlete {strava_athlete_id}: {updates}")
    # Update simple fields if present (e.g. title is not here, weight might be?)
    pass
