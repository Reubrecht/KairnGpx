
import sys
import os

# Add the parent directory to sys.path to allow importing app modules

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append("/app") # Ensure docker path is explicit


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import models
from app.database import SQLALCHEMY_DATABASE_URL
from passlib.context import CryptContext

# Setup password hashing
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)


import argparse

# ... (rest of imports)

def create_super_admin():
    parser = argparse.ArgumentParser(description="Create Super Admin")
    parser.add_argument("username", nargs="?", default="jerome", help="Username for super admin")

    args = parser.parse_args()

    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    username = args.username

    password = "123"
    email = f"{username}@kairn.app" 


    try:
        # Check if user exists
        existing_user = db.query(models.User).filter(models.User.username == username).first()
        
        if existing_user:
            print(f"User '{username}' already exists. Updating to Super Admin...")
            existing_user.role = models.Role.SUPER_ADMIN
            existing_user.is_admin = True
            existing_user.is_email_verified = True
            existing_user.hashed_password = get_password_hash(password)
            db.commit()
            print("User updated successfully.")
        else:
            print(f"Creating new Super Admin user '{username}'...")
            new_user = models.User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                role=models.Role.SUPER_ADMIN,
                is_admin=True,
                is_email_verified=True, # Bypass email verification
                full_name="Super Admin"
            )
            db.add(new_user)
            db.commit()
            print("User created successfully.")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_super_admin()
