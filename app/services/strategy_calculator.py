import math
from typing import List, Dict, Any, Optional
from .analytics import GpxAnalytics

class StrategyCalculator:
    def __init__(self, track_analytics: GpxAnalytics):
        self.analytics = track_analytics
        self.points = track_analytics.points
        # Cache full track length and metrics
        metrics = self.analytics.calculate_metrics()
        self.total_dist = metrics.get('distance_km', 0)
        self.total_elev_gain = metrics.get('elevation_gain', 0)

    def calculate_splits(self, target_time_minutes: int, waypoints: List[Dict[str, Any]], start_time_hour: float = 6.0) -> Dict[str, Any]:
        """
        Calculate splits based on Target Time and Topography Cost.
        
        Args:
            target_time_minutes: Total goal time in minutes.
            waypoints: List of dicts [{'km': 10, 'name': 'Point A'}, ...] (Must be sorted by KM)
            start_time_hour: Start time in decimal hours (e.g. 6.5 for 06:30)
            
        Returns:
            Dict containing 'segments' (splits between waypoints) and 'total_stats'.
        """
        if not self.points:
            return {}

        # 1. Resample Track into micro-segments (e.g. every 100m or existing points)
        # For variable density GPX, we should iterate points and accumulate cost.
        # Cost Formula (Energy Cost):
        # 1 km flat = 1 unit
        # 100m D+ = 1 km flat (10% gradient is 2x cost of flat?) -> Standard equivalent distance: Dist + D+/100
        # Slope penalty: steep slopes cost more energy per meter gained.
        
        # Micro-segment accumulation
        micro_segments = []
        
        cumulative_dist = 0.0
        last_p = self.points[0]
        cumulative_cost = 0.0
        
        # Prepare Waypoints: Ensure Start (0km) and End (Total) exist
        sorted_waypoints = sorted(waypoints, key=lambda x: float(x['km']))
        
        # Filter duplicates or out of bounds
        active_waypoints = []
        if not sorted_waypoints or abs(sorted_waypoints[0]['km']) > 0.1:
            active_waypoints.append({'km': 0.0, 'name': 'Départ', 'type': 'start'})
            
        for wp in sorted_waypoints:
            if 0 <= float(wp['km']) <= self.total_dist + 0.5: # Tolerance
                active_waypoints.append(wp)
                
        if not active_waypoints or abs(active_waypoints[-1]['km'] - self.total_dist) > 0.5:
             active_waypoints.append({'km': self.total_dist, 'name': 'Arrivée', 'type': 'finish'})

        # Map KM to waypoints for checking
        wp_indices = {i: wp for i, wp in enumerate(active_waypoints)}
        next_wp_idx = 1 # Start looking for the first stop (idx 0 is start)
        
        current_segment_stats = {
            "dist": 0.0,
            "d_plus": 0,
            "cost": 0.0
        }
        
        # Global stats storage
        segments_result = []
        
        total_track_cost = 0.0
        
        # Iteration state
        segment_costs = [] # To store cost of each inter-waypoint segment
        
        # We need to compute the COST of each segment first to distribute time.
        # But we also need detailed D+ stats for each segment.
        
        # Method: Single Pass - Accumulate stats until we hit a waypoint KM.
        
        seg_dist = 0
        seg_dplus = 0
        seg_cost = 0
        
        last_km_accum = 0
        
        # Iterate points
        # NOTE: self.points may be huge.
        
        current_wp_target = active_waypoints[next_wp_idx]
        
        for i in range(1, len(self.points)):
            p1 = self.points[i-1]
            p2 = self.points[i]
            
            dist_m = p1.distance_2d(p2)
            dist_km = dist_m / 1000.0
            cumulative_dist += dist_km
            
            ele_diff = (p2.elevation - p1.elevation) if (p1.elevation and p2.elevation) else 0
            d_plus_m = max(0, ele_diff)
            d_minus_m = max(0, -ele_diff)
            
            # --- COST CALCULATION ---
            # Base: Distance
            cost = dist_km
            
            # Elev Penalty: 100m D+ ~= 1km flat
            cost += (d_plus_m / 100.0)
            
            # Descent: Small cost or negative?
            # Technical descent is slow (cost positive). Runnable smooth is fast (cost negative/reduction).
            # Safety: Assume descent is neutral or slightly costly if steep.
            # Simplified: 400m D- ~= 1km flat in terms of TIME roughly for average trail runner (technical)
            # Actually, let's keep it simple: Equivalent Flat Distance.
            # Standard Effort km: Dist + D+/100.
            # We add a small factor for descent to avoid underestimating technical downhill time.
            # Let's say D- is 0 cost (free speed) creates too fast est.
            # Let's add D-/400 approx.
            # cost += (d_minus_m / 400.0) 
            
            # Slope Penalty (Steepness factor)
            # If slope > 20%, efficiency drops.
            slope = (ele_diff / dist_m * 100) if dist_m > 0 else 0
            if abs(slope) > 20:
                cost *= 1.2 # 20% penalty for very steep
                
            seg_dist += dist_km
            seg_dplus += d_plus_m
            seg_cost += cost
            total_track_cost += cost
            
            # CHECK WAYPOINT
            # If we passed the target waypoint KM
            if cumulative_dist >= float(current_wp_target['km']):
                # Close segment
                segment_costs.append({
                    "wp_start": active_waypoints[next_wp_idx-1],
                    "wp_end": current_wp_target,
                    "dist": seg_dist,
                    "d_plus": seg_dplus,
                    "cost": seg_cost
                })
                
                # Reset
                seg_dist = 0
                seg_dplus = 0
                seg_cost = 0
                
                next_wp_idx += 1
                if next_wp_idx < len(active_waypoints):
                    current_wp_target = active_waypoints[next_wp_idx]
                else:
                    break # All waypoints done
        
        # Handle cleanup if incomplete (due to GPX short or rounding)
        if next_wp_idx < len(active_waypoints):
             # Force close last segment
             segment_costs.append({
                "wp_start": active_waypoints[next_wp_idx-1],
                "wp_end": active_waypoints[next_wp_idx],
                "dist": seg_dist,
                "d_plus": seg_dplus,
                "cost": seg_cost
            })

        # --- TIME DISTRIBUTION ---
        # Total Cost * Factor = Target Time
        # Factor = Target / TotalCost
        if total_track_cost == 0: total_track_cost = 1 # Avoid div zero
        
        pace_factor = target_time_minutes / total_track_cost
        
        # --- FATIGUE SIMULATION ---
        # With fatigue, the "cost" of the final km is higher than the first.
        # We want to increase cost progressively.
        # Linear drift?
        # Let's Apply a drift factor to the pace_factor over the accumulation?
        # Simpler: Re-weight the segment costs.
        # Cost_i_weighted = Cost_i * (1 + (CumulativeCost_i / TotalCost) * FatiguePercent)
        
        FATIGUE_FACTOR = 0.20 # +20% effort cost by end of race
        
        weighted_total_cost = 0
        for seg in segment_costs:
            # Approx relative position
            # This is rough, ideally we integrate over micro-segments, but segment-level is okay for display.
            # Use current weighted_total as progress? No, use raw cost progress.
            progress = (weighted_total_cost / total_track_cost) if total_track_cost > 0 else 0
            
            # Drift: 1.0 -> 1.2
            drift = 1.0 + (progress * FATIGUE_FACTOR)
            
            seg['weighted_cost'] = seg['cost'] * drift
            # weighted_total_cost += seg['cost'] # Wait, progress should be based on RAW cost
            # But the sum for time distribution must be based on WEIGHTED cost.
            
        # Re-sum
        total_weighted_cost = sum(s['weighted_cost'] for s in segment_costs)
        
        # New Pace Factor
        real_pace_factor = target_time_minutes / total_weighted_cost
        
        # --- GENERATE OUTPUT ---
        
        current_time_min = 0
        start_hour_decimal = start_time_hour
        
        final_segments = []
        
        # Add Start Row
        current_tod = self._min_to_tod(start_hour_decimal * 60)
        
        # We need a list of Points, not segments, for the table usually.
        # But report requested "Roadbook" usually has intervals.
        # Let's provide a list of Points with "Arrive Time" and "Segment Previous Stats".
        
        # Point 0: Start
        final_points = [{
            "name": active_waypoints[0]['name'],
            "km": 0,
            "d_plus_cumul": 0,
            "time_race": "00:00",
            "time_day": current_tod,
            "segment_dist": 0,
            "segment_d_plus": 0,
            "segment_time": "-"
        }]
        
        cumul_d_plus = 0
        
        for seg in segment_costs:
            time_min = seg['weighted_cost'] * real_pace_factor
            current_time_min += time_min
            cumul_d_plus += seg['d_plus']
            
            tod_minutes = (start_hour_decimal * 60) + current_time_min
            
            final_points.append({
                "name": seg['wp_end']['name'],
                "km": round(float(seg['wp_end']['km']), 1),
                "d_plus_cumul": int(cumul_d_plus),
                "time_race": self._format_duration(current_time_min),
                "time_day": self._min_to_tod(tod_minutes),
                "segment_dist": round(seg['dist'], 1),
                "segment_d_plus": int(seg['d_plus']),
                "segment_time": self._format_duration(time_min)
            })
            
        return {
            "strategy": {
                "target_time": target_time_minutes,
                "fatigue_factor": FATIGUE_FACTOR
            },
            "points": final_points
        }

    def _format_duration(self, minutes):
        h = int(minutes // 60)
        m = int(minutes % 60)
        return f"{h:02d}h{m:02d}"

    def _min_to_tod(self, total_minutes):
        # Time of Day (e.g. 18:30)
        total_minutes = total_minutes % (24 * 60) # Wrap 24h
        h = int(total_minutes // 60)
        m = int(total_minutes % 60)
        return f"{h:02d}:{m:02d}"
