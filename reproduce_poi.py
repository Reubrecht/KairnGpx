
import requests
import json
import os

BASE_URL = "http://localhost:8000"

def run():
    # 1. Login/Create User (Need to check how to do this or if I can mock)
    # Since I don't have easy auth mock, I'll rely on inspecting the code logic I just read.
    # But I can try to use a mock DB session if I write a test inside the app structure.
    # Alternatively, I can just use python to inspect the DB directly using the app's models.
    
    import sys
    sys.path.append("/projet_dev_ssd/KairnGpx")
    from app import models, database
    from app.database import SessionLocal
    
    db = SessionLocal()
    
    # Check latest track
    track = db.query(models.Track).order_by(models.Track.id.desc()).first()
    if track:
        print(f"Track ID: {track.id}, Title: {track.title}")
        print(f"POIs Type: {type(track.points_of_interest)}")
        print(f"POIs Value: {track.points_of_interest}")
    else:
        print("No tracks found.")
        
    db.close()

if __name__ == "__main__":
    run()
