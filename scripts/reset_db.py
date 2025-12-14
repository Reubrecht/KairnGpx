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
