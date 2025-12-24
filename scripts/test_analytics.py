
import unittest
import sys
import os

# Add app to path
sys.path.append(os.getcwd())

from app.services.analytics import GpxAnalytics

class TestGpxAnalytics(unittest.TestCase):
    def setUp(self):
        # Create a simple GPX content
        self.gpx_content = b"""
        <gpx version="1.1" creator="Kairn" xmlns="http://www.topografix.com/GPX/1/1">
          <metadata>
            <name>Test Track</name>
            <desc>A nice test track</desc>
          </metadata>
          <trk>
            <name>Test Track</name>
            <trkseg>
              <trkpt lat="45.9237" lon="6.8684"><ele>1035</ele></trkpt>
              <trkpt lat="45.9240" lon="6.8690"><ele>1050</ele></trkpt>
              <trkpt lat="45.9250" lon="6.8700"><ele>1100</ele></trkpt>
            </trkseg>
          </trk>
        </gpx>
        """
        self.analytics = GpxAnalytics(self.gpx_content)

    def test_get_start_wkt(self):
        wkt = self.analytics.get_start_wkt()
        self.assertEqual(wkt, "POINT(6.8684 45.9237)")

    def test_infer_attributes(self):
        metrics = {
            "distance_km": 10,
            "elevation_gain": 500,
            "max_slope": 20,
            "avg_slope_uphill": 10,
            "max_altitude": 1500
        }
        attrs = self.analytics.infer_attributes(metrics)
        self.assertEqual(attrs["technicity_score"], 2) # max_slope 20 > 15 -> 2
        
        metrics_high = {
            "distance_km": 10,
            "elevation_gain": 1000,
            "max_slope": 40,
            "avg_slope_uphill": 15,
            "max_altitude": 2500
        }
        attrs_high = self.analytics.infer_attributes(metrics_high)
        self.assertEqual(attrs_high["technicity_score"], 4) # max_slope 40 > 35 -> 4
        
        # Exposure check
        metrics_sunny = {
            "distance_km": 10,
            "elevation_gain": 500,
            "max_altitude": 2200 # > 2000
        }
        attrs_sunny = self.analytics.infer_attributes(metrics_sunny)
        self.assertEqual(attrs_sunny["exposure"], "Ensoleillé")

if __name__ == '__main__':
    unittest.main()
