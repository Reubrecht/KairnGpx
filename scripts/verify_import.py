
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app import models
from app.database import SQLALCHEMY_DATABASE_URL

def verify_import():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        events = db.query(models.RaceEvent).count()
        editions = db.query(models.RaceEdition).count()
        routes = db.query(models.RaceRoute).count()
        
        print(f"📊 Verification Stats:")
        print(f"  Events: {events}")
        print(f"  Editions: {editions}")
        print(f"  Routes: {routes}")

    finally:
        db.close()

if __name__ == "__main__":
    verify_import()
