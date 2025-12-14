import sys
import os

# Add project root to path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, engine
from app import models
import datetime

# Setup DB
models.Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Check if dummy user exists
user = db.query(models.User).filter(models.User.username == "test_local").first()
if not user:
    user = models.User(username="test_local", email="test@local.com", hashed_password="hashed_password_dummy")
    db.add(user)
    db.commit()
    print("Created dummy user: test_local")

# Check if dummy track exists
track_title = "Trace de Test Locale"
track = db.query(models.Track).filter(models.Track.title == track_title).first()
if not track:
    # Basic dummy data simulating metric calculation
    track = models.Track(
        title=track_title,
        slug="trace-de-test-locale",
        description="Une trace pour tester l'affichage local.",
        user_id=user.username,
        distance_km=12.5,
        elevation_gain=450,
        elevation_loss=450,
        max_altitude=1200,
        min_altitude=800,
        avg_altitude=1000,
        start_lat=45.1885, # Grenoble approx
        start_lon=5.7245,
        status=models.StatusEnum.TRAINING,
        technicity=models.TechnicityEnum.PEU_TECHNIQUE,
        terrain=models.TerrainEnum.MIXTE,
        location_city="Grenoble",
        location_region="Auvergne-Rhône-Alpes",
        file_hash="dummy_hash_12345",
        file_path="app/uploads/dummy_hash_12345.gpx"
    )
    db.add(track)
    db.commit()
    print(f"Created dummy track: {track_title}")
    
    # Create a dummy GPX file for it so the map doesn't crash 404
    import os
    os.makedirs("app/uploads", exist_ok=True)
    with open("app/uploads/dummy_hash_12345.gpx", "w") as f:
        f.write("""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="KairnDummy">
  <trk>
    <name>Trace Test</name>
    <trkseg>
      <trkpt lat="45.1885" lon="5.7245"><ele>800</ele></trkpt>
      <trkpt lat="45.1890" lon="5.7250"><ele>850</ele></trkpt>
      <trkpt lat="45.1900" lon="5.7260"><ele>900</ele></trkpt>
      <trkpt lat="45.1910" lon="5.7270"><ele>1100</ele></trkpt>
      <trkpt lat="45.1920" lon="5.7280"><ele>1200</ele></trkpt>
      <trkpt lat="45.1885" lon="5.7245"><ele>800</ele></trkpt>
    </trkseg>
  </trk>
</gpx>""")

else:
    print("Dummy track already exists.")

db.close()
