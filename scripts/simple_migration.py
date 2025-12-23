import os
import sys

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
from sqlalchemy import inspect, text

def run_migration():
    inspector = inspect(engine)
    
    # 1. Create table event_owners if not exists
    if not inspector.has_table("event_owners"):
        print("Creating table 'event_owners'...")
        # Create specifically this table
        # We need to access the Table object from metadata
        from app.models import event_owners
        event_owners.create(engine)
        print("Table 'event_owners' created.")
    else:
        print("Table 'event_owners' already exists.")

    # 2. Add columns to race_events
    # Check columns in race_events
    columns = [c['name'] for c in inspector.get_columns("race_events")]
    
    with engine.connect() as conn:
        if "profile_picture" not in columns:
            print("Adding column 'profile_picture' to 'race_events'...")
            conn.execute(text("ALTER TABLE race_events ADD COLUMN profile_picture VARCHAR"))
            conn.commit()
        
        if "contact_link" not in columns:
            print("Adding column 'contact_link' to 'race_events'...")
            conn.execute(text("ALTER TABLE race_events ADD COLUMN contact_link VARCHAR"))
            conn.commit()

    # 3. Add columns to tracks
    track_columns = [c['name'] for c in inspector.get_columns("tracks")]
    with engine.connect() as conn:
        if "thumbnail_url" not in track_columns:
            print("Adding column 'thumbnail_url' to 'tracks'...")
            conn.execute(text("ALTER TABLE tracks ADD COLUMN thumbnail_url VARCHAR"))
            conn.commit()

    # 4. Add columns to race_strategies
    if inspector.has_table("race_strategies"):
        strat_columns = [c['name'] for c in inspector.get_columns("race_strategies")]
        with engine.connect() as conn:
            if "nutrition_strategy" not in strat_columns:
                print("Adding column 'nutrition_strategy' to 'race_strategies'...")
                conn.execute(text("ALTER TABLE race_strategies ADD COLUMN nutrition_strategy TEXT"))
                conn.commit()

            
    print("Migration check complete.")

if __name__ == "__main__":
    print("Starting migration...")
    run_migration()
