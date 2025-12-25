from app.database import SessionLocal
from app import models

db = SessionLocal()
total_tracks = db.query(models.Track).count()
tracks_with_technicity = db.query(models.Track).filter(models.Track.technicity_score != None).count()
tracks_without_technicity = total_tracks - tracks_with_technicity

print(f"Total Tracks: {total_tracks}")
print(f"Tracks with Technicity: {tracks_with_technicity}")
print(f"Tracks without Technicity: {tracks_without_technicity}")

# Simulate the filter
min_tech = 1
filtered_tracks = []
all_tracks = db.query(models.Track).all()
for t in all_tracks:
    if t.technicity_score is None or t.technicity_score < min_tech:
        continue
    filtered_tracks.append(t)

print(f"Tracks remaining with min_technicity={min_tech}: {len(filtered_tracks)}")
