import sys
import argparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import models
from app.database import SQLALCHEMY_DATABASE_URL

def create_super_admin(username):
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            print(f"❌ User '{username}' not found.")
            return

        print(f"found user: {user.username} (Role: {user.role}, Is Admin: {user.is_admin})")
        
        user.role = models.Role.SUPER_ADMIN
        user.is_admin = True # Legacy support
        db.commit()
        
        print(f"✅ User '{username}' is now SUPER_ADMIN.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote a user to Super Admin.")
    parser.add_argument("username", help="The username of the user to promote")
    args = parser.parse_args()
    
    create_super_admin(args.username)
