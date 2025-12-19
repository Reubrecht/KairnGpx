import os
import sys

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app import models

def check_track(track_id):
    db = SessionLocal()
    try:
        print(f"Checking Track ID: {track_id}...")
        track = db.query(models.Track).filter(models.Track.id == track_id).first()
        if track:
            print(f"FOUND Track {track.id}")
            print(f"Title: {track.title}")
            print(f"User ID: {track.user_id}")
            print(f"File Path: {track.file_path}")
            print(f"Visibility: {track.visibility}")
            print(f"Created At: {track.created_at}")
        else:
            print(f"Track {track_id} NOT FOUND in DB.")
            
        # Also list last 5 tracks
        print("\nLast 5 Tracks:")
        tracks = db.query(models.Track).order_by(models.Track.id.desc()).limit(5).all()
        for t in tracks:
            print(f" - ID: {t.id} | Title: {t.title}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        tid = int(sys.argv[1])
        check_track(tid)
    else:
        # Default to a recent ID check if none provided, or just list
        check_track(55) # Hardcoded based on user report
