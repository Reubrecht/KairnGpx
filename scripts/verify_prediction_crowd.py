import sys
import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path
sys.path.append(os.getcwd())

from app import models
from app.services.prediction import RaceTimePredictor
from app.services.prediction_config_manager import PredictionConfigManager

# MOCK DB SETUP (InMemory SQLite)
from sqlalchemy.ext.declarative import declarative_base
Base = models.Base

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

def run_verification():
    print("--- Verifying Crowd Prediction Logic ---")

    # 1. Create Data
    # User 1 (The Reviewer/Runner)
    u1 = models.User(username="runner1", utmb_index=500, itra_score=500)
    # User 2 (The Predictor/Me)
    u2 = models.User(username="me", utmb_index=500, itra_score=500)
    
    # Track
    track = models.Track(
        title="Test Track",
        distance_km=10.0,
        elevation_gain=1000,
        slug="test-track"
    )
    
    db.add_all([u1, u2, track])
    db.commit()

    # 2. Baseline Prediction (No history)
    # Physics: 10km + 1000m = 20 km-effort.
    # Index 500 -> ~5.0 km-effort/h (simplification, real formula depends on config)
    # Approx 4h?
    pred_base = RaceTimePredictor.predict(track, u2)
    base_time_h = pred_base["raw_hours"]["race"]
    print(f"Baseline Time (No history): {base_time_h} hours")
    print(f"Reality Factor: {pred_base.get('reality_factor', 'N/A')}")
    
    # 3. Add an Execution that is SLOWER (Reality check)
    # Let's say User 1 ran it in 2x the base time.
    # If base is 4h, he ran in 8h.
    # Theoretical for U1 (same index) is same as base (~4h).
    # Ratio = 8 / 4 = 2.0.
    
    duration_seconds = int(base_time_h * 3600 * 2.0)
    execution = models.TrackExecution(
        track_id=track.id,
        user_id=u1.id,
        duration_seconds=duration_seconds,
        execution_date=datetime.datetime.utcnow()
    )
    db.add(execution)
    db.commit()
    
    # Reload track relations?
    # SQLAlchemy might need refresh if not committed/expired, but we committed.
    # Accessing track.executions should trigger lazy load.
    
    # 4. Predict Again
    pred_corrected = RaceTimePredictor.predict(track, u2)
    corrected_time_h = pred_corrected["raw_hours"]["race"]
    factor = pred_corrected["reality_factor"]
    
    print(f"\nCorrected Time (With 1 execution 2x slower): {corrected_time_h} hours")
    print(f"Reality Factor: {factor}")
    print(f"Sample Size: {pred_corrected['sample_size']}")

    # Verification
    # Expected factor is close to 2.0
    if 1.9 <= factor <= 2.1:
        print("\n[SUCCESS] Correction Factor is within expected range (~2.0)")
    else:
        print(f"\n[FAILURE] Correction Factor {factor} is NOT within expected range (~2.0)")

    if corrected_time_h > base_time_h:
         print("[SUCCESS] Corrected time is higher than baseline.")
    else:
         print("[FAILURE] Corrected time is NOT higher than baseline.")

if __name__ == "__main__":
    run_verification()
