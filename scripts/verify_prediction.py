import sys
import os

# Add project root to path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models import User, Track
from app.services.prediction import RaceTimePredictor

def test_prediction():
    # Mock Data
    user_novice = User(username="novice", utmb_index=350)
    user_avg = User(username="avg", utmb_index=500)
    user_elite = User(username="elite", utmb_index=800)
    
    # 1. Standard Trail (40km, 2000m D+) -> KmEffort = 60
    track_trail = Track(distance_km=40, elevation_gain=2000)
    
    # 2. Flat Run (10km, 50m D+) -> KmEffort = 10.5
    track_flat = Track(distance_km=10, elevation_gain=50)
    
    # 3. Skyrace (20km, 2000m D+) -> KmEffort = 40, Steep (100m/km)
    track_sky = Track(distance_km=20, elevation_gain=2000)

    scenarios = [
        (user_avg, track_trail, "Average User - 40km Trail"),
        (user_elite, track_trail, "Elite User - 40km Trail"),
        (user_novice, track_flat, "Novice User - 10km Flat"),
        (user_avg, track_sky, "Average User - 20km Skyrace (Steep)"),
    ]

    print(f"{'Scenario':<40} | {'VO2':<5} | {'Race Time':<10} | {'Endurance':<10} | {'Push':<10}")
    print("-" * 85)
    
    for user, track, label in scenarios:
        res = RaceTimePredictor.predict(track, user)
        # res['times'] has {race, endurance, push} strings
        print(f"{label:<40} | {res['vo2max_est']:<5} | {res['times']['race']:<10} | {res['times']['endurance']:<10} | {res['times']['push']:<10}")

if __name__ == "__main__":
    test_prediction()
