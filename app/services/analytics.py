import gpxpy
import math
from typing import Dict, Any, List, Tuple
from datetime import timedelta

class GpxAnalytics:
    def __init__(self, gpx_content: bytes):
        try:
            # Force utf-8 decoding if strictly bytes
            if isinstance(gpx_content, bytes):
                try:
                    gpx_string = gpx_content.decode('utf-8')
                except UnicodeDecodeError:
                    gpx_string = gpx_content.decode('latin-1')
            else:
                gpx_string = gpx_content
                
            self.gpx = gpxpy.parse(gpx_string)
            self.points = []
            for track in self.gpx.tracks:
                for segment in track.segments:
                    self.points.extend(segment.points)
                    
        except Exception as e:
            print(f"Error parsing GPX: {e}")
            self.gpx = None
            self.points = []

    def simplify_track(self, epsilon: float = 0.0001) -> str:
        """
        Simplify the track using Douglas-Peucker algorithm to reduce points.
        Returns the new simplified GPX XML string.
        epsilon: tolerance (approx 10m for 0.0001 degrees)
        """
        if not self.gpx:
            return ""
        
        # Clone to avoid mutating original if needed elsewhere (though gpxpy mutates)
        # We simplify strictly for display/storage optimization if requested
        self.gpx.simplify()
        return self.gpx.to_xml()

    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Calculate extensive metrics including slopes, altitudes, and effort.
        """
        if not self.gpx or not self.points:
            return {}

        # 1. Basic Stats (from gpxpy)
        moving_data = self.gpx.get_moving_data()
        uphill, downhill = self.gpx.get_uphill_downhill()
        
        distance_2d = self.gpx.length_2d()
        distance_km = round(distance_2d / 1000, 2)
        
        # 2. Altitude Stats
        elevations = [p.elevation for p in self.points if p.elevation is not None]
        if elevations:
            max_alt = int(max(elevations))
            min_alt = int(min(elevations))
            avg_alt = int(sum(elevations) / len(elevations))
        else:
            max_alt = min_alt = avg_alt = 0

        # 3. Slope Analysis
        # Calculate slope between points separated by ~50m to smooth noise
        slopes = []
        uphill_slopes = []
        
        # Simple iterator with step
        # Note: accurate slope requires proper distance calculation between points
        # taking a sample every X points is a rough approximation if density varies
        # Better: iterate and accumulate distance until > 50m
        
        accumulated_dist = 0
        last_p = self.points[0]
        
        for p in self.points[1:]:
            dist = last_p.distance_2d(p)
            accumulated_dist += dist
            
            if accumulated_dist >= 50: # Analyze every 50m chunk
                ele_diff = (p.elevation - last_p.elevation) if (p.elevation and last_p.elevation) else 0
                if dist > 0:
                    slope_pct = (ele_diff / accumulated_dist) * 100
                    slopes.append(slope_pct)
                    if slope_pct > 0:
                        uphill_slopes.append(slope_pct)
                
                # Reset
                last_p = p
                accumulated_dist = 0

        max_slope = round(max(slopes), 1) if slopes else 0
        avg_slope_uphill = round(sum(uphill_slopes) / len(uphill_slopes), 1) if uphill_slopes else 0

        # 4. Effort Calculations
        elevation_gain = int(uphill)
        elevation_loss = int(downhill)
        
        # Km Effort (Standard: Dist + D+/100)
        km_effort = round(distance_km + (elevation_gain / 100), 1)
        
        # ITRA Points (Approximate table)
        # < 25: 0, 25-39: 1, 40-64: 2, 65-89: 3, 90-139: 4, 140-189: 5, >190: 6
        itra = 0
        if km_effort >= 25: itra = 1
        if km_effort >= 40: itra = 2
        if km_effort >= 65: itra = 3
        if km_effort >= 90: itra = 4
        if km_effort >= 140: itra = 5
        if km_effort >= 190: itra = 6

        # 5. Estimated Times
        # Hiker: 4km/h flat + 300m/h ascent
        # Runner: 8km/h flat + 600m/h ascent (Basic runner)
        # Elite: 12km/h flat + 1200m/h ascent
        
        def format_duration(hours):
            h = int(hours)
            m = int((hours - h) * 60)
            return f"{h}h{m:02d}"

        t_hiker_h = (distance_km / 4) + (elevation_gain / 300)
        t_runner_h = (distance_km / 8) + (elevation_gain / 600)
        t_elite_h = (distance_km / 12) + (elevation_gain / 1200)

        estimated_times = {
            "hiker": format_duration(t_hiker_h),
            "runner": format_duration(t_runner_h),
            "elite": format_duration(t_elite_h)
        }

        # 6. Route Type Detection
        start_p = self.points[0]
        end_p = self.points[-1]
        dist_start_end = start_p.distance_2d(end_p)
        
        route_type = "point_to_point"
        if dist_start_end < 200: # Ends within 200m of start
            route_type = "loop"
        
        return {
            "distance_km": distance_km,
            "elevation_gain": elevation_gain,
            "elevation_loss": elevation_loss,
            "max_altitude": max_alt,
            "min_altitude": min_alt,
            "avg_altitude": avg_alt,
            "max_slope": max_slope,
            "avg_slope_uphill": avg_slope_uphill,
            "km_effort": km_effort,
            "itra_points_estim": itra,
            "route_type": route_type,
            "estimated_times": estimated_times,
            "start_coords": (start_p.latitude, start_p.longitude),
            "end_coords": (end_p.latitude, end_p.longitude)
        }
