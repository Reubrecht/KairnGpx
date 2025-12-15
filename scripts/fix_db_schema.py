import os
import sys
from sqlalchemy import create_engine, text

# Add the parent directory to the path so we can import app if needed, 
# but here we just need the DB connection string.
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Use the same logic as app/database.py to get the URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app/data/kairn.db")

deploy_mode = "postgres" in DATABASE_URL or "postgis" in DATABASE_URL

print(f"Connecting to database: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)

def run_migration():
    with engine.connect() as connection:
        # Start transaction
        trans = connection.begin()
        try:
            print("Beginning schema update...")
            
            # List of columns to add to 'users' table
            # format: (column_name, data_type)
            columns_to_add = [
                ("profile_picture", "TEXT"),
                ("location", "TEXT"),
                ("location_city", "TEXT"),
                ("location_region", "TEXT"),
                ("location_country", "TEXT"),
                ("location_lat", "FLOAT"),
                ("location_lon", "FLOAT"),
                ("website", "TEXT"),
                ("strava_url", "TEXT"),
                ("social_links", "JSON"),
                ("profile_picture_url", "TEXT"),
                ("age", "INTEGER"),
                ("height", "INTEGER"),
                ("weight", "FLOAT"),
                ("gender", "TEXT"),
                ("max_heart_rate", "INTEGER"),
                ("resting_heart_rate", "INTEGER"),
                ("vo2_max", "FLOAT"),
                ("ftp", "INTEGER"),
                ("lthr", "INTEGER"),
                ("hr_zones", "JSON"),
                ("power_zones", "JSON"),
                ("weight_history", "JSON"),
                ("club_affiliation", "TEXT"),
                ("is_certified_guide", "BOOLEAN DEFAULT FALSE"),
                ("itra_score", "INTEGER"),
                ("utmb_index", "INTEGER"),
                ("betrail_score", "FLOAT"),
                ("favorite_activity", "TEXT"),
                ("achievements", "JSON"),
            ]

            for col_name, col_type in columns_to_add:
                try:
                    print(f"Adding column '{col_name}'...")
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type};"))
                except Exception as e:
                    print(f"Skipping {col_name} (might exist or error): {e}")

            # Special handling for Geometry
            if deploy_mode:
                try:
                    print("Adding 'location_geom'...")
                    # ensure extension exists
                    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                    connection.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS location_geom GEOMETRY(POINT, 4326);"))
                except Exception as e:
                    print(f"Error adding geometry: {e}")

            trans.commit()
            print("Schema update completed successfully!")
        except Exception as e:
            trans.rollback()
            print(f"Migration failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    run_migration()
