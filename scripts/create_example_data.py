
import sys
import os
import shutil
import hashlib
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append("/app") 

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import models
from app.database import SQLALCHEMY_DATABASE_URL
from app.utils import slugify

def create_example_data():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        print("Creating Example Data...")
        
        # 1. Create Event
        event_name = "Grand Raid des Pyrenees"
        event_slug = slugify(event_name)
        
        event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == event_slug).first()
        if not event:
            print(f"Creating Event: {event_name}")
            event = models.RaceEvent(
                name=event_name,
                slug=event_slug,
                description="Une course mythique dans les Pyrénées.",
                region="Occitanie",
                continent="Europe",
                country="France",
                department="Hautes-Pyrénées",
                massif="Pyrénées",
                city="Vielle-Aure"
            )
            db.add(event)
            db.commit()
            db.refresh(event)
        else:
            print(f"Event {event_name} already exists.")

        # 2. Create Edition
        year = 2025
        edition = db.query(models.RaceEdition).filter(models.RaceEdition.event_id == event.id, models.RaceEdition.year == year).first()
        if not edition:
            print(f"Creating Edition: {year}")
            edition = models.RaceEdition(
                event_id=event.id,
                year=year,
                status=models.RaceStatus.UPCOMING
            )
            db.add(edition)
            db.commit()
            db.refresh(edition)
        
        # 3. Create Track from GPX
        gpx_source = "/app/scripts/example_trace.gpx"
        if not os.path.exists(gpx_source):
             # Try local path if not in docker
             gpx_source = "scripts/example_trace.gpx"
             
        if os.path.exists(gpx_source):
            with open(gpx_source, 'rb') as f:
                content = f.read()
            
            file_hash = hashlib.sha256(content).hexdigest()
            
            # Move/Copy to upload dir
            upload_dir = "/app/app/uploads"
            if not os.path.exists(upload_dir):
                os.makedirs(upload_dir, exist_ok=True)
                
            dest_path = os.path.join(upload_dir, f"{file_hash}.gpx")
            with open(dest_path, 'wb') as f:
                f.write(content)
            
            track_title = "Tour du Pic du Jer"
            slug = slugify(track_title)
            
            track = db.query(models.Track).filter(models.Track.slug == slug).first()
            if not track:
                print(f"Creating Track: {track_title}")
                # Mock metrics for this simple file
                track = models.Track(
                    title=track_title,
                    slug=slug,
                    description="Trace officielle du Tour du Pic.",
                    user_id=None, # System track or assign to admin if needed
                    uploader_name="System",
                    activity_type=models.ActivityType.TRAIL_RUNNING,
                    is_official_route=True,
                    distance_km=10.5,
                    elevation_gain=800,
                    elevation_loss=800,
                    file_path=dest_path,
                    file_hash=file_hash,
                    visibility=models.Visibility.PUBLIC,
                    verification_status=models.VerificationStatus.VERIFIED_HUMAN,
                    start_lat=43.0900,
                    start_lon=-0.0500,
                    location_city="Lourdes",
                    location_region="Occitanie",
                    location_country="France"
                )
                db.add(track)
                db.commit()
                db.refresh(track)
            
            # 4. Create Race Route
            route_name = "Tour du Pic 10K"
            route = db.query(models.RaceRoute).filter(models.RaceRoute.edition_id == edition.id, models.RaceRoute.name == route_name).first()
            if not route:
                print(f"Creating Race Route: {route_name}")
                route = models.RaceRoute(
                    edition_id=edition.id,
                    name=route_name,
                    distance_category="10K",
                    official_track_id=track.id,
                    distance_km=10.5,
                    elevation_gain=800
                )
                db.add(route)
                db.commit()
                print("Data creation complete.")
            else:
                print("Race Route already exists.")
        else:
            print(f"GPX file not found at {gpx_source}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_example_data()
