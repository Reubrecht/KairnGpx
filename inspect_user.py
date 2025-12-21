import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app import models

def inspect_user():
    db = SessionLocal()
    try:
        username = "zach"
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            print(f"User found: {user.username}")
            print(f"Role: {user.role} (Type: {type(user.role)})")
            print(f"Is Admin (Legacy): {user.is_admin}")
            print(f"Enum Value: {user.role.value if hasattr(user.role, 'value') else 'N/A'}")
        else:
            print(f"User {username} not found.")
    except Exception as e:
        print(f"Error inspecting user: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    inspect_user()
