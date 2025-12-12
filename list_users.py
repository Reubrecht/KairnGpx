
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import models
from app.database import SQLALCHEMY_DATABASE_URL

def list_users():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        users = db.query(models.User).all()
        print(f"Found {len(users)} users:")
        for user in users:
            print(f"ID: {user.id}, Username: {user.username}, Role: {user.role}, IsAdmin: {user.is_admin}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_users()
