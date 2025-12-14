import sys
import os

# Add project root to path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import engine
from app.models import Base

print("Deleting all tables...")
try:
    Base.metadata.drop_all(bind=engine)
    print("Tables deleted.")
    
    print("Recreating tables...")
    Base.metadata.create_all(bind=engine)
    print("Database reset successfully.")
except Exception as e:
    print(f"Error resetting database: {e}")
