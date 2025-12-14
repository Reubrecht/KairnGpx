from typing import Dict, Any, Optional
from .. import models
from .prediction_config_manager import PredictionConfigManager

class RaceTimePredictor:
    """
    Predicts race time based on track metrics and user performance index (UTMB/ITRA/Betrail).
    """

    @staticmethod
    def predict(track: models.Track, user: models.User) -> Dict[str, Any]:
        """
        Calculate predicted times for different intensity levels.
        Returns a dict with formatted times and metadata.
        """
        
        cfg = PredictionConfigManager.get_config()
        
        # Override with user config if premium
        if user and user.is_premium and user.prediction_config:
            # Shallow merge is enough for now, or deep merge if nested
            # user.prediction_config is a dict from JSON column
            cfg = {**cfg, **user.prediction_config}
        
        
        # 1. Determine User Performance Index
        indices = []
        if user.utmb_index: indices.append(user.utmb_index)
        if user.itra_score: indices.append(user.itra_score)
        if user.betrail_score: indices.append(int(user.betrail_score)) 
        
        user_index = max(indices) if indices else 400 
        
        # 2. Key Metrics
        dist = track.distance_km or 0
        elev = track.elevation_gain or 0
        if dist == 0:
            return {}

        # Km Effort (Standard Formula: Dist + D+/100)
        km_effort = dist + (elev / 100.0)
        
        # Gradient Ratio (Technicality Proxy)
        # m per km
        gradient_ratio = elev / dist if dist > 0 else 0
        
        # 3. Scientific Extrapolations
        # VO2max Estimate
        vo2max_est = round(user_index / 11.6, 1)
        
        # Base Speed on Flat (km-effort/h)
        # Formula: Speed = Slope * Index - Intercept
        base_speed_kmeh = (cfg["base_speed_slope"] * user_index) - cfg["base_speed_intercept"]
        if base_speed_kmeh < cfg["min_speed_kmeh"]: base_speed_kmeh = cfg["min_speed_kmeh"]
        
        # 4. Correction Factors
        
        # A. Technicality / Steepness Penalty
        tech_factor = 1.0
        if gradient_ratio > cfg["tech_factor_1_threshold"]: 
            tech_factor = cfg["tech_factor_1_hilly"]
        if gradient_ratio > cfg["tech_factor_2_threshold"]: 
            tech_factor = cfg["tech_factor_2_mountain"]
        if gradient_ratio > cfg["tech_factor_3_threshold"]: 
            tech_factor = cfg["tech_factor_3_alpine"]
            
        # B. Distance Decay (Fatigue)
        dist_factor = 1.0
        if km_effort > cfg["decay_start_km"]:
            over_dist = km_effort - cfg["decay_start_km"]
            decay_pct = (over_dist / cfg["decay_step_km"]) * cfg["decay_rate_per_step"]
            if decay_pct > cfg["decay_max_total"]: 
                decay_pct = cfg["decay_max_total"]
            dist_factor = 1.0 - decay_pct

        # Apply Factors
        adjusted_speed = base_speed_kmeh * tech_factor * dist_factor
        if adjusted_speed < 2.5: adjusted_speed = 2.5 # Absolute floor logic preserved
        
        # 5. Calculate Times for 3 Intensities
        def format_time(hours):
            if hours > 99: return ">99h"
            h = int(hours)
            m = int((hours - h) * 60)
            return f"{h}h{m:02d}"

        # Scenario 1: Endurance
        t_endurance_h = km_effort / (adjusted_speed * cfg["endurance_multiplier"]) 
        
        # Scenario 2: Race (Objective)
        t_race_h = km_effort / adjusted_speed
        
        # Scenario 3: Push 
        t_push_h = km_effort / (adjusted_speed * cfg["push_multiplier"]) 
        
        return {
            "prediction_available": True,
            "user_index": user_index,
            "vo2max_est": vo2max_est,
            "km_effort": round(km_effort, 1),
            "times": {
                "endurance": format_time(t_endurance_h),
                "race": format_time(t_race_h),
                "push": format_time(t_push_h)
            },
            "raw_hours": {
                "race": round(t_race_h, 2)
            }
        }
