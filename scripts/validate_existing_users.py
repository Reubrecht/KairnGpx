import sys
import os
from dotenv import load_dotenv

# Add the project root to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Load environment using the same priority as the app (local.env first)
env_path = os.path.join(os.path.dirname(__file__), '../local.env')
if os.path.exists(env_path):
    print(f"Loading environment from {env_path}")
    load_dotenv(env_path)
else:
    print("No local.env found, relying on system environment variables")

from app.database import SessionLocal, engine
from app.models import User

def validate_all_emails():
    # Verify connection
    db_url = os.getenv("DATABASE_URL", "NOT_SET")
    if "sqlite" in db_url:
        print(f"WARNING: Connecting to SQLite database at {db_url}")
        print("If you intended to connect to PostgreSQL, ensure DATABASE_URL is set.")
    else:
        # Mask password for display
        safe_url = db_url.split("@")[-1] if "@" in db_url else "..."
        print(f"Connecting to Database: ...@{safe_url}")

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_email_verified == False).all()
        count = len(users)
        
        if count == 0:
            print("No unverified users found.")
            return

        print(f"Found {count} unverified users. Updating...")
        
        for user in users:
            user.is_email_verified = True
        
        db.commit()
        print(f"Successfully verified {count} users.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    validate_all_emails()
