import sys
import os
# Add the project root to the python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def manual_load_env(path):
    """Fallback to manually parse .env file if python-dotenv is missing"""
    print(f"Manually loading environment from {path}")
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                os.environ[key] = value
    except Exception as e:
        print(f"Failed to manually load .env: {e}")

# Load environment using the same priority as the app (local.env first)
env_path = os.path.join(os.path.dirname(__file__), '../local.env')

try:
    from dotenv import load_dotenv
    if os.path.exists(env_path):
        print(f"Loading environment from {env_path} using python-dotenv")
        load_dotenv(env_path)
    else:
        print("No local.env found, relying on system environment variables")
except ImportError:
    print("python-dotenv not found. Attempting manual load.")
    if os.path.exists(env_path):
        manual_load_env(env_path)
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
