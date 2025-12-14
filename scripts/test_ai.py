import sys
import os

# Add project root to path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.ai_analyzer import AiAnalyzer
import os
from dotenv import load_dotenv

load_dotenv('local.env')

analyzer = AiAnalyzer()
metrics = {
    "distance_km": 10.5,
    "elevation_gain": 500,
    "max_altitude": 1200,
    "route_type": "loop",
    "max_slope": 15,
    "km_effort": 15.5
}
print("Test with gemini-2.0-flash...")
result = analyzer.analyze_track(metrics)
print(result)
