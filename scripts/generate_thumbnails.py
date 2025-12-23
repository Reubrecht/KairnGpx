
import sys
import os
import time

# Add app to path
sys.path.append(os.getcwd())

from app.database import SessionLocal, engine
from app import models
from app.services.thumbnail_generator import ThumbnailGenerator
from sqlalchemy import text

def add_column_if_not_exists():
    try:
        with engine.connect() as conn:
            # Check if column exists
            # This is a basic check for SQLite/Postgres compatibility layers often used in simple scripts
            # But specific syntax varies. 
            # Safe way: try to select it, if fail, add it.
            try:
                conn.execute(text("SELECT thumbnail_url FROM tracks LIMIT 1"))
                print("Column 'thumbnail_url' already exists.")
            except Exception:
                print("Column 'thumbnail_url' missing. Adding it...")
                conn.execute(text("ALTER TABLE tracks ADD COLUMN thumbnail_url VARCHAR"))
                conn.commit()
                print("Column added.")
    except Exception as e:
        print(f"Schema update warning: {e}")

def main():
    print("Ensure schema is up to date...")
    # Try to add column manually if alembic fails or just to be safe in dev
    add_column_if_not_exists()
    
    print("Starting thumbnail generation...")
    db = SessionLocal()
    
    try:
        tracks = db.query(models.Track).filter(models.Track.thumbnail_url == None).all()
        print(f"Found {len(tracks)} tracks processing...")
        
        generator = ThumbnailGenerator()
        count = 0
        
        for track in tracks:
            if not track.file_path or not os.path.exists(track.file_path):
                print(f"Skipping track {track.id}: File not found at {track.file_path}")
                continue
                
            print(f"Generating for track {track.id}: {track.title}")
            try:
                thumb_url = generator.generate_thumbnail(track.file_path, track.id)
                if thumb_url:
                    track.thumbnail_url = thumb_url
                    db.commit()
                    count += 1
                else:
                    print(f"Failed to generate for {track.id}")
            except Exception as e:
                print(f"Error on track {track.id}: {e}")
                
        print(f"Completed! Generated {count} thumbnails.")
        
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
