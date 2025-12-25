import sys
import os

# Add the project root to the python path so we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import SessionLocal
from app.models import User

def validate_all_emails():
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_email_verified == False).all()
        count = 0
        for user in users:
            user.is_email_verified = True
            count += 1
        
        db.commit()
        print(f"Successfully validated email for {count} users.")
    except Exception as e:
        print(f"An error occurred: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    validate_all_emails()
