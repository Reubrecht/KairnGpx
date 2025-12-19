
import unittest
from datetime import datetime
from app.routers.strava_auth import convert_streams_to_gpx
import xml.etree.ElementTree as ET

class TestStravaGpxConversion(unittest.TestCase):
    def test_convert_streams_to_gpx(self):
        # Mock Activity Data
        activity_data = {
            "name": "Test Run",
            "start_date": "2023-10-27T10:00:00Z",
            "distance": 1000,
            "total_elevation_gain": 50
        }
        
        # Mock Streams (list format as returned by API before dict conversion inside function if needed,
        # but function handles both. Let's pass list format)
        streams = [
            {
                "type": "latlng",
                "data": [[45.0, 6.0], [45.001, 6.001], [45.002, 6.002]]
            },
            {
                "type": "altitude",
                "data": [100.0, 105.0, 110.0]
            },
            {
                "type": "time",
                "data": [0, 10, 20] # Seconds from start
            },
            {
                "type": "heartrate",
                "data": [140, 145, 150]
            }
        ]
        
        gpx_bytes = convert_streams_to_gpx(activity_data, streams)
        
        # Verify it's not empty
        self.assertTrue(len(gpx_bytes) > 0)
        
        # Verify XML structure
        root = ET.fromstring(gpx_bytes)
        
        # Check Namespaces (ElementTree adds ns0 usually if xmlns is present)
        # We can search by stripping namespace or just checking tags
        
        # Check Name
        # Find 'name' in metadata (namespaces make find tricky)
        # Using simple string check for simplicity or iterative find
        
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
        
        # Check Metadata Name
        meta_name = root.find('.//gpx:metadata/gpx:name', ns)
        self.assertEqual(meta_name.text, "Test Run")
        
        # Check Points
        trkpts = root.findall('.//gpx:trkpt', ns)
        self.assertEqual(len(trkpts), 3)
        
        # Check Point 1
        p1 = trkpts[0]
        self.assertEqual(p1.get("lat"), "45.0")
        self.assertEqual(p1.get("lon"), "6.0")
        self.assertEqual(p1.find("gpx:ele", ns).text, "100.0")
        
        # Check Time 
        # 2023-10-27T10:00:00Z + 0s
        self.assertEqual(p1.find("gpx:time", ns).text, "2023-10-27T10:00:00Z")
        
        # Check HR extension
        # ElementTree namespacing for extensions is tricky if not defined in root.
        # Our function generates: <extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>...
        # We can just check p1 string content or children
        # extensions = p1.find("gpx:extensions", ns) # This might fail if extended namespace not registered in parsing
        
        # Let's check raw string for HR presence
        gpx_str = gpx_bytes.decode('utf-8')
        self.assertIn("<gpxtpx:hr>140</gpxtpx:hr>", gpx_str)
        self.assertIn("<gpxtpx:hr>150</gpxtpx:hr>", gpx_str)

if __name__ == '__main__':
    unittest.main()
