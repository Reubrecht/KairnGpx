import os
import sys
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.models import Base

# Get Database URL from env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL is not set.")
    sys.exit(1)

print(f"Connecting to database: {DATABASE_URL}")

def init_db():
    engine = create_engine(DATABASE_URL)
    
    # Retry logic for connection
    retries = 30
    for i in range(retries):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database connection successful.")
            break
        except Exception as e:
            if i < retries - 1:
                print(f"Waiting for database... ({e})")
                time.sleep(2)
            else:
                print("Could not connect to database.")
                raise e

    print("Creating tables...")
    # This will create all tables defined in models.py
    # If using PostGIS, ensure the extension is enabled. 
    # The docker image 'postgis/postgis' usually has it, but let's be safe.
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
            conn.commit()
            print("PostGIS extension enabled.")
        except Exception as e:
            print(f"Warning: Could not enable PostGIS extension (might already be enabled or permission error): {e}")

    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
