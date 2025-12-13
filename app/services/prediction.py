from typing import Dict, Any, Optional
from .. import models

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
        
        # 1. Determine User Performance Index
        # We take the max of available indices to be optimistic/accurate to potential
        indices = []
        if user.utmb_index: indices.append(user.utmb_index)
        if user.itra_score: indices.append(user.itra_score)
        if user.betrail_score: indices.append(int(user.betrail_score)) # Betrail is float usually
        
        user_index = max(indices) if indices else 400 # Default to 400 (Novice/Beginner) if nothing
        
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
        # VO2max Estimate (Approximation: Index / 11.6 or similar)
        # 400 -> 34 ml/kg/min
        # 800 -> 69 ml/kg/min
        vo2max_est = round(user_index / 11.6, 1)
        
        # Base Speed on Flat (km-effort/h)
        # Linear regression approx: 
        # 300 Index -> ~3.5 km/h
        # 500 Index -> ~8.0 km/h (Run-Walk)
        # 800 Index -> ~15.0 km/h
        # Formula: Speed = 0.024 * Index - 4 
        # Check: 500 * 0.024 = 12 - 4 = 8. Correct.
        # Check: 800 * 0.024 = 19.2 - 4 = 15.2. Correct.
        # Check: 400 * 0.024 = 9.6 - 4 = 5.6. Plausible.
        base_speed_kmeh = (0.024 * user_index) - 4
        if base_speed_kmeh < 3: base_speed_kmeh = 3 # Minimum hiking speed fallback
        
        # 4. Correction Factors
        
        # A. Technicality / Steepness Penalty
        # If very steep, even km-effort is harder than flat.
        tech_factor = 1.0
        if gradient_ratio > 40: # > 40m/km = Hilly
            tech_factor = 0.95
        if gradient_ratio > 60: # > 60m/km = Mountain
            tech_factor = 0.85
        if gradient_ratio > 90: # > 90m/km = Very Technical/Vertical
            tech_factor = 0.70
            
        # B. Distance Decay (Fatigue)
        # Longer races = slower avg speed
        # Decay starts > 40km?
        # Simple Riegel-like factor? Or simpler decrement.
        # Let's reduce speed by 5% every 20km beyond 40km?
        dist_factor = 1.0
        if km_effort > 40:
            # e.g. at 60km, we are 20km over. reduce 5%.
            # at 100km, we are 60km over. reduce 15%.
            over_dist = km_effort - 40
            decay_pct = (over_dist / 20) * 0.05
            if decay_pct > 0.4: decay_pct = 0.4 # Cap decay at 40%
            dist_factor = 1.0 - decay_pct

        # Apply Factors
        adjusted_speed = base_speed_kmeh * tech_factor * dist_factor
        if adjusted_speed < 2.5: adjusted_speed = 2.5 # Absolute floor
        
        # 5. Calculate Times for 3 Intensities
        
        # Function to format hours
        def format_time(hours):
            if hours > 99: return ">99h"
            h = int(hours)
            m = int((hours - h) * 60)
            return f"{h}h{m:02d}"

        # Scenario 1: Endurance / Cool (65% of Max Capacity?)
        # Actually usually "Endurance" pace is ~70-75% of race pace? 
        # Or let's say User Index is their "Max Race Potential". 
        # So "Cool" is running as if Index was -100 pts? Or speed * 0.8?
        # Let's use Speed scale.
        t_endurance_h = km_effort / (adjusted_speed * 0.85) # Slower
        
        # Scenario 2: Race (Objective) -> The predicted time
        t_race_h = km_effort / adjusted_speed
        
        # Scenario 3: Push / Challenge (110% intensity or short segment pace)
        t_push_h = km_effort / (adjusted_speed * 1.15) # 15% Faster
        
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
