import sys
import os
# Add root to python path
sys.path.append(os.getcwd())

from app import database, models
from app.services.prediction import RaceTimePredictor
from app.services.prediction_config_manager import PredictionConfigManager

# 1. Get Admin User
db = next(database.get_db())
user = db.query(models.User).filter(models.User.is_admin == True).first()
if not user:
    # helper
    user = models.User(username="test_admin", is_admin=True, is_premium=True)
    db.add(user)
    db.commit()

print(f"User: {user.username}")

# 2. Set User Config (Personal Override)
user.prediction_config = {"endurance_multiplier": 0.1} # Extreme value
db.commit()

# 3. Set Global Config
global_cfg = PredictionConfigManager.get_config()
global_cfg["endurance_multiplier"] = 0.9 # Normal value
PredictionConfigManager.save_config(global_cfg)

# 4. Mock Track
track = models.Track(distance_km=10, elevation_gain=0)

# 5. Predict
result = RaceTimePredictor.predict(track, user)
# Time = Dist / (Speed * Mult)
# If mult is 0.1, time should be huge.
# If mult is 0.9, time should be normal.

print(f"Prediction Config Used (Implicitly):")
# We calculate back the multiplier used? 
# Or just print user.prediction_config vs PredictionConfigManager.get_config()

print(f"User DB Config: {user.prediction_config['endurance_multiplier']}")
print(f"Global File Config: {PredictionConfigManager.get_config()['endurance_multiplier']}")

# We need to see what RaceTimePredictor actually used.
# Since it merges inside variables, we can't see the cfg dict directly without modifying code.
# But we can infer.
# Base Speed approx 8-12kmh. 
# 10km / (10 * 0.1) = 10 hours.
# 10km / (10 * 0.9) = 1.1 hours.
print(f"Endurance Time: {result['times']['endurance']}")

# Clean up
user.prediction_config = None
db.commit()
