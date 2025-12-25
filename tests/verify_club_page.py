import sys
import os
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Add app to path
sys.path.append(os.getcwd())

from app.main import app
from app import models
from app.dependencies import get_current_user_optional, get_db

# Mock User
mock_user = models.User(
    id=1,
    username="testuser",
    email="test@example.com",
    club_affiliation="Test Club",
    profile_picture=None,
    full_name="Test User"
)

# Mock DB
mock_db = MagicMock()

# Mock Dependency Override for DB only
def override_get_db():
    yield mock_db

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_club_page_structure():
    print("Testing /club endpoint structure...")
    
    # Patch get_current_user_optional where it is USED
    with patch("app.routers.club.get_current_user_optional", return_value=mock_user) as mock_auth:
        
        # 1. Mock DB queries in club.py
        # We need to be careful mainly about the 'members' query and the stats loop
        mock_members = [mock_user]
        
        # Setup mock_query
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        
        # 1. members = ...all()
        mock_query.all.return_value = mock_members
        
        # 2. stats = ...first()
        mock_stats = MagicMock()
        mock_stats.total_dist = 123000.0 # 123 km
        mock_stats.total_elev = 1500.0
        mock_stats.total_time = 7200 # 2h
        mock_query.first.return_value = mock_stats
        
        # Make request
        response = client.get("/club")
        
        assert response.status_code == 200
        html = response.text
        
        # Check Filters
        if "Période:" in html and "Semaine" in html and "Mois" in html:
            print("✅ Filter 'Période' found")
        else:
            print("❌ Filter 'Période' MISSING")
            
        if "Classement:" in html and "Distance" in html and "Dénivelé" in html:
            print("✅ Filter 'Classement' found")
        else:
            print("❌ Filter 'Classement' MISSING")
            
        # Check Table Headers
        if "Athlète" in html and "Distance" in html and "Temps" in html:
            print("✅ Leaderboard Headers found")
        else:
             print("❌ Leaderboard Headers MISSING")
             
        # Check Data
        if "123.0" in html: # 123 km
            print("✅ Stats Data (123.0 km) found in table")
        else:
            print("❌ Stats Data MISSING")
        
def test_club_filters():
    print("\nTesting /club filters...")
    
    with patch("app.routers.club.get_current_user_optional", return_value=mock_user):
        # Test with params
        response = client.get("/club?period=year&metric=elevation")
        assert response.status_code == 200
        html = response.text
        
        # Check if 'Année' is active
        # The template applies a class logic. We check if the params are preserved in links, usually a good proxy.
        if "period=year" in html and "metric=elevation" in html:
            print("✅ Query params preserved in links")
        
    print("Verification of endpoints DONE.")

if __name__ == "__main__":
    try:
        test_club_page_structure()
        test_club_filters()
    except Exception as e:
        print(f"❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
