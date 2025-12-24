import sys
import os
import asyncio
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.main import app
from app.dependencies import get_db
from app.models import User, Role

# Setup Database connection
DATABASE_URL = "postgresql://kairn:kairn_password@localhost:5432/kairn"
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Get real user to return
db = TestingSessionLocal()
real_user = db.query(User).filter(User.username == "jerome").first()
db.close()

if not real_user:
    print("User jerome not found")
    sys.exit(1)

# Patching get_current_user in app.routers.tracks
# It must be an async function
async def mock_get_current_user(request, db):
    return real_user

print("Patching get_current_user...")
with patch("app.routers.tracks.get_current_user", side_effect=mock_get_current_user):
    client = TestClient(app)
    print("Attempting to access GET /upload ...")
    try:
        response = client.get("/upload")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 500:
            print("Content (Error):") # uvicorn usually suppresses 500 details in response but TestClient might catch it
            # Actually TestClient raises the exception if it's not handled by an exception handler
        else:
            print("Success!")
            # print(response.text[:200])
    except Exception as e:
        print("CAUGHT EXCEPTION DURING REQUEST:")
        import traceback
        traceback.print_exc()
