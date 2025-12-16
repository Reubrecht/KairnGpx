import os
import httpx
from fastapi import APIRouter, Request, status, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from .. import models
from ..dependencies import get_db

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
    """
    print(f"Processing new activity {activity_id} for athlete {strava_athlete_id}")
    # TODO: Implement logic to find user, get token, fetch GPX, save Track
    # This duplicates logic in strava_auth.import_strava_route but needs to run isolated.
    pass

async def process_athlete_update(strava_athlete_id: int, updates: dict):
    print(f"Processing update for athlete {strava_athlete_id}: {updates}")
    # Update simple fields if present (e.g. title is not here, weight might be?)
    pass
