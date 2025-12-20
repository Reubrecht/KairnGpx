import sys
import os

# Add parent dir to path to import app
sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models

def cleanup_events():
    db = SessionLocal()
    try:
        print("Starting cleanup...")
        
        # 1. Unlink Tracks
        # Find all routes with official tracks
        routes = db.query(models.RaceRoute).filter(models.RaceRoute.official_track_id != None).all()
        track_ids = [r.official_track_id for r in routes]
        
        print(f"Found {len(routes)} routes with linked tracks.")
        
        if track_ids:
            # Update these tracks
            # We fetch them to update ORM flags easily
            tracks = db.query(models.Track).filter(models.Track.id.in_(track_ids)).all()
            for t in tracks:
                t.is_official_route = False
                # t.verification_status = models.VerificationStatus.VERIFIED_HUMAN # Keep verified? Or revert? 
                # User said "sans supprimer les traces". Usually they are just traces now.
                # Let's keep them public if they were public, just not "official".
            
            db.commit()
            print(f"Updated {len(tracks)} tracks to remove official status.")

        # 2. Delete Routes
        deleted_routes = db.query(models.RaceRoute).delete()
        print(f"Deleted {deleted_routes} race routes.")
        
        # 3. Delete Editions
        deleted_editions = db.query(models.RaceEdition).delete()
        print(f"Deleted {deleted_editions} race editions.")
        
        # 4. Delete Events
        deleted_events = db.query(models.RaceEvent).delete()
        print(f"Deleted {deleted_events} race events.")
        
        # 5. Delete Event Requests (Optional but clean)
        deleted_requests = db.query(models.EventRequest).delete()
        print(f"Deleted {deleted_requests} event requests.")

        db.commit()
        print("Cleanup complete.")
        
    except Exception as e:
        print(f"Error during cleanup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_events()
