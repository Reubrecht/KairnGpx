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

    def calculate_splits(
        self, 
        target_time_minutes: int, 
        waypoints: List[Dict[str, Any]], 
        start_time_hour: float = 6.0,
        fatigue_factor: float = 1.0,
        technicity_score: float = 1.0
    ) -> Dict[str, Any]:
        """
        Calculate splits based on Target Time and Topography Cost.
        Includes Aggressive and Conservative pacing strategies.
        """
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
        next_wp_idx = 1 # Start looking for the first stop (idx 0 is start)
        
        segment_costs = [] # To store cost of each inter-waypoint segment
        
        # Method: Single Pass - Accumulate stats until we hit a waypoint KM.
        seg_dist = 0
        seg_dplus = 0
        seg_dminus = 0
        seg_cost = 0
        
        current_wp_target = active_waypoints[next_wp_idx]
        cumulative_dist = 0.0
        
        total_track_cost = 0.0

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
            # Simplified: Equivalent Flat Distance.
            # Standard Effort km: Dist + D+/100.
            
            # Slope Penalty (Steepness factor)
            slope = (ele_diff / dist_m * 100) if dist_m > 0 else 0
            if abs(slope) > 20:
                cost *= 1.2 # 20% penalty for very steep
                
            seg_dist += dist_km
            seg_dplus += d_plus_m
            seg_dminus += d_minus_m # Accumulate D-
            seg_cost += cost
            total_track_cost += cost
            
            # CHECK WAYPOINT
            if cumulative_dist >= float(current_wp_target['km']):
                # Close segment
                segment_costs.append({
                    "wp_start": active_waypoints[next_wp_idx-1],
                    "wp_end": current_wp_target,
                    "dist": seg_dist,
                    "d_plus": seg_dplus,
                    "d_minus": seg_dminus,
                    "cost": seg_cost,
                    "end_altitude": p2.elevation or 0 # Capture altitude
                })
                
                # Reset
                seg_dist = 0
                seg_dplus = 0
                seg_dminus = 0
                seg_cost = 0
                
                next_wp_idx += 1
                if next_wp_idx < len(active_waypoints):
                    current_wp_target = active_waypoints[next_wp_idx]
                else:
                    break # All waypoints done
        
        # Handle cleanup if incomplete
        if next_wp_idx < len(active_waypoints):
             segment_costs.append({
                "wp_start": active_waypoints[next_wp_idx-1],
                "wp_end": active_waypoints[next_wp_idx],
                "dist": seg_dist,
                "d_plus": seg_dplus,
                "d_minus": seg_dminus,
                "cost": seg_cost,
                "end_altitude": self.points[-1].elevation or 0
            })

        # --- TIME DISTRIBUTION ---
        # 1. Main Strategy (User Input)
        main_times = self._distribute_time(segment_costs, target_time_minutes, fatigue_factor)
        
        # 2. Aggressive Strategy (Fast Start, Slow End) -> High Fatigue Factor
        # Simulates going out too hard (e.g., +25% drift)
        agg_times = self._distribute_time(segment_costs, target_time_minutes, 1.25)
        
        # 3. Conservative Strategy (Even Splits) -> Zero Fatigue drift
        cons_times = self._distribute_time(segment_costs, target_time_minutes, 1.0)
        
        # --- GENERATE OUTPUT ---
        
        current_tod = self._min_to_tod(start_time_hour * 60)
        
        # Point 0: Start
        final_points = [{
            "name": active_waypoints[0]['name'],
            "km": 0,
            "altitude": int(self.points[0].elevation or 0),
            "d_plus_cumul": 0,
            "time_race": "00:00",
            "time_day": current_tod,
            "time_fast_tod": current_tod,
            "time_slow_tod": current_tod,
            "segment_dist": 0,
            "segment_d_plus": 0,
            "segment_d_minus": 0,
             "segment_time": "-"
        }]
        
        cumul_d_plus = 0
        cumul_time = 0
        cumul_time_agg = 0
        cumul_time_cons = 0
        
        for i, seg in enumerate(segment_costs):
            # Main
            time_seg = main_times[i]
            cumul_time += time_seg
            
            # Strategies
            time_seg_agg = agg_times[i]
            cumul_time_agg += time_seg_agg
            
            time_seg_cons = cons_times[i]
            cumul_time_cons += time_seg_cons
            
            cumul_d_plus += seg['d_plus']
            
            # Format TODs
            tod_minutes = (start_time_hour * 60) + cumul_time
            tod_agg = (start_time_hour * 60) + cumul_time_agg
            tod_cons = (start_time_hour * 60) + cumul_time_cons

            final_points.append({
                "name": seg['wp_end']['name'],
                "km": round(float(seg['wp_end']['km']), 1),
                "altitude": int(seg.get('end_altitude', 0)),
                "d_plus_cumul": int(cumul_d_plus),
                "time_race": self._format_duration(cumul_time),
                "time_day": self._min_to_tod(tod_minutes),
                "segment_dist": round(seg['dist'], 1),
                "segment_d_plus": int(seg['d_plus']),
                "segment_d_minus": int(seg['d_minus']),
                "segment_time": self._format_duration(time_seg),
                
                # UTMB Columns: Fast (Aggressive) vs Slow (Conservative)
                "time_fast_tod": self._min_to_tod(tod_agg),
                "time_slow_tod": self._min_to_tod(tod_cons),
                
                # Pass through extras
                "type": seg['wp_end'].get('type', 'ravito'),
                "lat": seg['wp_end'].get('lat'),
                "lon": seg['wp_end'].get('lon'),
            })
            
        return {
            "strategy": {
                "target_time": target_time_minutes,
                "fatigue_factor": fatigue_factor
            },
            "points": final_points
        }

    def _distribute_time(self, segment_costs, target_time, fatigue_factor):
        """
        Distribute target_time across segments based on cost and fatigue factor.
        Returns a list of time_in_minutes for each segment.
        """
        if not segment_costs: return []
        
        total_track_cost = sum(s['cost'] for s in segment_costs)
        if total_track_cost == 0: total_track_cost = 1
        
        weighted_costs = []
        weighted_total = 0
        
        # Calculate Drifts
        current_weighted_progress = 0 # Using raw cost for progress approximation
        
        for seg in segment_costs:
            progress = (current_weighted_progress / total_track_cost)
            
            # Linear Drift: 1.0 -> fatigue_factor
            drift = 1.0 + (progress * (fatigue_factor - 1.0))
            
            w_cost = seg['cost'] * drift
            weighted_costs.append(w_cost)
            weighted_total += w_cost
            
            current_weighted_progress += seg['cost']
            
        # Normalize to target time
        pace_factor = target_time / weighted_total
        
        times = [w * pace_factor for w in weighted_costs]
        return times

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
