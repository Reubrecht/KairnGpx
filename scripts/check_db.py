import sys
import os

# Add project root to path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import SQLALCHEMY_DATABASE_URL
from app import models

engine = create_engine(SQLALCHEMY_DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

events = db.query(models.RaceEvent).count()
editions = db.query(models.RaceEdition).count()
routes = db.query(models.RaceRoute).count()
print(f"Events: {events}, Editions: {editions}, Routes: {routes}")
db.close()
