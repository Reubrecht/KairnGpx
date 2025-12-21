from typing import Dict, Any, Optional
from .. import models
from .prediction_config_manager import PredictionConfigManager

class RaceTimePredictor:
    """
    Predicts race time based on track metrics and user performance index (UTMB/ITRA/Betrail).
    """

    @staticmethod
    def _calculate_theoretical_seconds(track: models.Track, user_index: int, cfg: Dict[str, Any]) -> float:
        """
        Helper: Calculate purely theoretical Race time in seconds for a specific index.
        Matches the 'Scientific Extrapolations' + 'Correction Factors' logic from original predict.
        """
        # 2. Key Metrics
        dist = track.distance_km or 0
        elev = track.elevation_gain or 0
        if dist == 0:
            return 0.0

        # Km Effort
        km_effort = dist + (elev / 100.0)
        
        # Gradient Ratio
        gradient_ratio = elev / dist if dist > 0 else 0
        
        # Base Speed
        base_speed_kmeh = (cfg["base_speed_slope"] * user_index) - cfg["base_speed_intercept"]
        if base_speed_kmeh < cfg["min_speed_kmeh"]: base_speed_kmeh = cfg["min_speed_kmeh"]
        
        # Tech Correction
        tech_factor = 1.0
        if gradient_ratio > cfg["tech_factor_1_threshold"]: 
            tech_factor = cfg["tech_factor_1_hilly"]
        if gradient_ratio > cfg["tech_factor_2_threshold"]: 
            tech_factor = cfg["tech_factor_2_mountain"]
        if gradient_ratio > cfg["tech_factor_3_threshold"]: 
            tech_factor = cfg["tech_factor_3_alpine"]
            
        # Dist Correction
        dist_factor = 1.0
        if km_effort > cfg["decay_start_km"]:
            over_dist = km_effort - cfg["decay_start_km"]
            decay_pct = (over_dist / cfg["decay_step_km"]) * cfg["decay_rate_per_step"]
            if decay_pct > cfg["decay_max_total"]: 
                decay_pct = cfg["decay_max_total"]
            dist_factor = 1.0 - decay_pct

        # Adjusted Speed
        adjusted_speed = base_speed_kmeh * tech_factor * dist_factor
        if adjusted_speed < 2.5: adjusted_speed = 2.5 
        
        # Result in Hours -> Seconds
        t_race_h = km_effort / adjusted_speed
        return t_race_h * 3600.0

    @staticmethod
    def predict(track: models.Track, user: models.User) -> Dict[str, Any]:
        """
        Calculate predicted times for different intensity levels.
        Now includes 'Reality Factor' based on community executions.
        Only available for TRAIL_RUNNING and RUNNING.
        """
        # 0. Check Activity Type
        allowed_activities = [models.ActivityType.TRAIL_RUNNING, models.ActivityType.RUNNING]
        if track.activity_type not in allowed_activities:
            return {"prediction_available": False}

        
        cfg = PredictionConfigManager.get_config()
        
        # Override with user config if premium
        if user and user.is_premium and user.prediction_config:
            cfg = {**cfg, **user.prediction_config}
        
        # 1. Determine User Performance Index
        indices = []
        if user.utmb_index: indices.append(user.utmb_index)
        if user.itra_score: indices.append(user.itra_score)
        if user.betrail_score: indices.append(int(user.betrail_score)) 
        
        user_index = max(indices) if indices else 400 
        
        # 2. Calculate Theoretical Time (Base)
        base_seconds = RaceTimePredictor._calculate_theoretical_seconds(track, user_index, cfg)
        if base_seconds <= 0:
            return {}

        # 3. Calculate Crowd Correction Factor (Reality Factor)
        reality_factor = 1.0
        ratio_sum = 0.0
        ratio_count = 0
        
        # Use a fresh config for historical comparison to be consistent (fairness)
        # or use the same config? Using global standard config for historical analysis is safer 
        # to avoid bias from the current user's specific settings.
        std_cfg = PredictionConfigManager.get_config()

        if track.executions:
            for exc in track.executions:
                # We need the user index of the person who executed
                if not exc.user: continue
                
                u_indices = []
                if exc.user.utmb_index: u_indices.append(exc.user.utmb_index)
                if exc.user.itra_score: u_indices.append(exc.user.itra_score)
                if exc.user.betrail_score: u_indices.append(int(exc.user.betrail_score))
                
                # If unknown user level, we can't really use this data point reliably for physics calc
                # Skipping is better than guessing 400
                if not u_indices: continue
                
                u_idx = max(u_indices)
                
                theo_sec = RaceTimePredictor._calculate_theoretical_seconds(track, u_idx, std_cfg)
                if theo_sec > 0:
                    ratio = exc.duration_seconds / theo_sec
                    # Filter outliers: strict 0.5x to 2.0x range? 
                    # If I run 2x slower than predicted -> 2.0. If 2x faster -> 0.5.
                    if 0.4 <= ratio <= 2.5:
                        ratio_sum += ratio
                        ratio_count += 1
        
        # Apply correction if we have enough data
        if ratio_count >= 1: # Start correction from 1 execution? or 3? Let's say 1 for instant feedback
            avg_ratio = ratio_sum / ratio_count
            
            # Dampen the factor?
            # If average ratio is 1.2 (track is 20% slower than physics says), 
            # maybe we trust it 50%? 
            # reality_factor = 1.0 + ((avg_ratio - 1.0) * 0.8) 
            # Let's trust it fully for now
            reality_factor = avg_ratio

        corrected_seconds = base_seconds * reality_factor

        # 4. Derive Intensities
        # Re-derive hours
        t_race_h = corrected_seconds / 3600.0
        
        # Recalculate speed from this new time to apply multipliers
        # km_effort = dist + d+/100
        dist = track.distance_km or 0
        elev = track.elevation_gain or 0
        km_effort = dist + (elev / 100.0)
        
        final_speed = km_effort / t_race_h if t_race_h > 0 else 1
        
        # Endurance
        t_endurance_h = km_effort / (final_speed * cfg["endurance_multiplier"]) 
        # Push 
        t_push_h = km_effort / (final_speed * cfg["push_multiplier"]) 
        
        # 5. Output
        def format_time(hours):
            if hours > 99: return ">99h"
            h = int(hours)
            m = int((hours - h) * 60)
            return f"{h}h{m:02d}"

        return {
            "prediction_available": True,
            "user_index": user_index,
            "vo2max_est": round(user_index / 11.6, 1),
            "km_effort": round(km_effort, 1),
            "times": {
                "endurance": format_time(t_endurance_h),
                "race": format_time(t_race_h),
                "push": format_time(t_push_h)
            },
            "raw_hours": {
                "race": round(t_race_h, 2)
            },
            "reality_factor": round(reality_factor, 2),
            "sample_size": ratio_count
        }
