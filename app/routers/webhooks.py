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

        # 4. Filter Logic (Allowed Types Only)
        activity_type = activity_details.get("type")
        is_trainer = activity_details.get("trainer", False)

        allowed_types = ["Run", "TrailRun", "Ride", "GravelRide", "MountainBikeRide"]

        if activity_type not in allowed_types:
            print(f"Skipping activity {activity_id}: Type '{activity_type}' not in allowed list.")
            return

        if is_trainer or activity_type in ["VirtualRide", "VirtualRun"]:
            print(f"Skipping activity {activity_id}: Virtual activity detected.")
            return

        # 5. Fetch Streams
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
            print(f"Skipping activity {activity_id}: No GPS streams available.")
            return

        streams = streams_resp.json()

        # Extract Coordinates
        start_lat, start_lon = None, None
        end_lat, end_lon = None, None

        if "latlng" in streams and "data" in streams["latlng"] and len(streams["latlng"]["data"]) > 0:
            coords_data = streams["latlng"]["data"]
            start_lat, start_lon = coords_data[0]
            end_lat, end_lon = coords_data[-1]

        if not start_lat or not start_lon:
             print(f"Skipping activity {activity_id}: No valid coordinates.")
             return

        # Geocode Location
        city, region, country = utils.get_location_info(start_lat, start_lon)

        # 6. Convert to GPX
        gpx_content = convert_streams_to_gpx(activity_details, streams)
        if not gpx_content:
            print(f"Skipping activity {activity_id}: Could not generate GPX.")
            return

        # 7. Analytics
        analytics = GpxAnalytics(gpx_content)
        metrics = analytics.calculate_metrics()

        if not metrics:
            print(f"Skipping activity {activity_id}: Could not calculate metrics.")
            return

        # 8. AI Analysis & Metadata
        final_title = activity_details.get("name", f"Strava Activity {activity_id}")
        final_description = activity_details.get("description", "")
        inferred_tags = []

        try:
            ai_analyzer = AiAnalyzer()
            if ai_analyzer.model:
                gpx_meta = analytics.get_metadata()
                ai_data = ai_analyzer.analyze_track(
                    metrics,
                    metadata=gpx_meta,
                    user_title=final_title,
                    user_description=final_description
                )

                if ai_data.get("ai_description"):
                    final_description = ai_data["ai_description"]
                if ai_data.get("ai_tags"):
                    inferred_tags.extend(ai_data["ai_tags"])
        except Exception as e:
            print(f"AI Analysis failed for {activity_id}: {e}")

        # 9. Save Track
        filename = f"strava_activity_{activity_id}.gpx"
        save_path = f"app/uploads/{filename}"
        os.makedirs("app/uploads", exist_ok=True)

        with open(save_path, "wb") as f:
            f.write(gpx_content)

        file_hash = utils.calculate_file_hash(gpx_content)

        existing = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
        if existing:
            print(f"Activity {activity_id} already exists as Track {existing.id}.")
            return

        # Map Type
        db_activity_type = models.ActivityType.OTHER
        type_map = {
            "Run": models.ActivityType.RUNNING,
            "TrailRun": models.ActivityType.TRAIL_RUNNING,
            "Ride": models.ActivityType.ROAD_CYCLING,
            "GravelRide": models.ActivityType.GRAVEL,
            "MountainBikeRide": models.ActivityType.MTB_CROSS_COUNTRY
        }
        if activity_type in type_map:
            db_activity_type = type_map[activity_type]

        new_track = models.Track(
            title=final_title,
            description=final_description,
            user_id=user.id,
            uploader_name=user.username,
            source_type=models.SourceType.STRAVA_IMPORT,
            file_path=f"app/uploads/{filename}",
            file_hash=file_hash,
            visibility=models.Visibility.PRIVATE, # Default to Private

            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            location_city=city,
            location_region=region,
            location_country=country,

            distance_km=metrics["distance_km"],
            elevation_gain=metrics["elevation_gain"],
            elevation_loss=metrics["elevation_loss"],
            max_altitude=metrics["max_altitude"],
            min_altitude=metrics["min_altitude"],
            avg_altitude=metrics["avg_altitude"],

            max_slope=metrics["max_slope"],
            avg_slope_uphill=metrics["avg_slope_uphill"],
            km_effort=metrics["km_effort"],
            itra_points_estim=metrics["itra_points_estim"],
            ibp_index=metrics.get("ibp_index"),
            longest_climb=metrics.get("longest_climb"),

            route_type=metrics["route_type"],
            estimated_times=metrics["estimated_times"],

            tags=inferred_tags,
            activity_type=db_activity_type
        )

        db.add(new_track)
        db.commit()
        print(f"Successfully imported Activity {activity_id} as Track {new_track.id}")

    except Exception as e:
        print(f"Error processing activity {activity_id}: {e}")
        db.rollback()
    finally:
        db.close()

async def process_athlete_update(strava_athlete_id: int, updates: dict):
    print(f"Processing update for athlete {strava_athlete_id}: {updates}")
    # Update simple fields if present (e.g. title is not here, weight might be?)
    pass
