import sys
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import datetime
from sqlalchemy import inspect

# Add app to path
sys.path.append(os.getcwd())

from app import models
from app.database import SessionLocal, engine, Base
from app.routers import webhooks

# Ensure table creation
models.Base.metadata.create_all(bind=engine)

print("--- DB Inspection ---")
inspector = inspect(engine)
print(f"Tables in DB: {inspector.get_table_names()}")

# Mock Data
MOCK_ACTIVITY_ID = 1234567890
MOCK_ATHLETE_ID = 987654321
MOCK_ACTIVITY_DATA = {
    "id": MOCK_ACTIVITY_ID,
    "name": "Morning Run",
    "distance": 10500.0, # 10.5km
    "moving_time": 3600, # 1h
    "elapsed_time": 3800,
    "total_elevation_gain": 150.0,
    "type": "Run",
    "start_date": "2023-10-27T08:00:00Z"
}

async def run_verification():
    print("--- Starting Verification ---")
    
    db = SessionLocal()
    
    # 1. Setup Test User & Connection
    user = db.query(models.User).filter(models.User.username == "test_club_user").first()
    if not user:
        user = models.User(username="test_club_user", email="test@club.com", club_affiliation="Test Team")
        db.add(user)
        db.commit()
    
    # Ensure OAuthConnection exists
    conn = db.query(models.OAuthConnection).filter(models.OAuthConnection.provider_user_id == str(MOCK_ATHLETE_ID)).first()
    if not conn:
        conn = models.OAuthConnection(
            user_id=user.id,
            provider=models.OAuthProvider.STRAVA,
            provider_user_id=str(MOCK_ATHLETE_ID),
            access_token="fake_token"
        )
        db.add(conn)
        db.commit()
        
    # 2. Mock External Calls
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock() 
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Mock Response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_ACTIVITY_DATA
        
        mock_client.get.return_value = mock_resp 
        
        # Mock Token Validation
        with patch("app.routers.webhooks.get_valid_token", return_value="fake_token"):
            
            print(f"Calling process_new_activity({MOCK_ACTIVITY_ID}, {MOCK_ATHLETE_ID})...")
            # 3. Call The Function
            await webhooks.process_new_activity(MOCK_ACTIVITY_ID, MOCK_ATHLETE_ID)
            
    # 4. Verify Results
    print("\n--- Verifying Database ---")
    
    # Check StravaActivity
    activity = db.query(models.StravaActivity).filter(models.StravaActivity.strava_id == str(MOCK_ACTIVITY_ID)).first()
    if activity:
        print(f"✅ StravaActivity Found: ID={activity.id}")
        print(f"   Name: {activity.name}")
        print(f"   Dist: {activity.distance}m")
        print(f"   Elev: {activity.total_elevation_gain}m")
    else:
        print(f"❌ StravaActivity NOT Found!")
        
    # Check Track (Should NOT exist)
    try:
        track = db.query(models.Track).filter(models.Track.title == "Morning Run").order_by(models.Track.created_at.desc()).first()
        
        if track:
             # Check if created just now (allow some clock skew, say last 1 minute)
             if (datetime.datetime.utcnow() - track.created_at).total_seconds() < 60:
                 print(f"❌ Track Found (Unexpected): {track.title} (ID: {track.id})")
             else:
                 print(f"✅ No New Track Created (Old tracks with same name might exist)")
        else:
            print(f"✅ No Track Created (Expected)")
    except Exception as e:
        print(f"⚠️ Could not check for Tracks (likely schema mismatch in dev DB): {e}")

    # Cleanup
    if activity:
        db.delete(activity)
    db.commit()
    db.close()
    print("--- Verification Complete ---")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_verification())
