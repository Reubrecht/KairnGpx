import json
import os
from pathlib import Path

# Use absolute path relative to where app is run, or __file__
# Assuming app is run from root, 'app/prediction_config.json'
# Better to use __file__ relative
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "prediction_config.json"

DEFAULT_CONFIG = {
    "base_speed_slope": 0.024,
    "base_speed_intercept": 4.0,
    "min_speed_kmeh": 3.0,
    "tech_factor_1_threshold": 40,
    "tech_factor_1_hilly": 0.95,
    "tech_factor_2_threshold": 60,
    "tech_factor_2_mountain": 0.85,
    "tech_factor_3_threshold": 90,
    "tech_factor_3_alpine": 0.70,
    "decay_start_km": 40,
    "decay_step_km": 20,
    "decay_rate_per_step": 0.05,
    "decay_max_total": 0.40,
    "endurance_multiplier": 0.85,
    "push_multiplier": 1.15
}

class PredictionConfigManager:
    @staticmethod
    def get_config() -> dict:
        if not CONFIG_PATH.exists():
            PredictionConfigManager.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        
        try:
            with open(CONFIG_PATH, "r") as f:
                data = json.load(f)
                # Ensure all keys exist (merge with default if missing)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return DEFAULT_CONFIG

    @staticmethod
    def save_config(config: dict):
        # Validate keys roughly
        safe_config = {}
        for k in DEFAULT_CONFIG.keys():
            if k in config:
                safe_config[k] = float(config[k]) # Ensure numbers
            else:
                safe_config[k] = DEFAULT_CONFIG[k]
                
        with open(CONFIG_PATH, "w") as f:
            json.dump(safe_config, f, indent=4)
