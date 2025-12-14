import sys
import os
from sqlalchemy import create_engine, text

# Add parent directory to path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SQLALCHEMY_DATABASE_URL

def add_profile_picture_column():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    print(f"🔌 Connecting to database...")
    with engine.connect() as connection:
        try:
            print("📦 Adding 'profile_picture' column to 'users' table...")
            
            alter_query = text("ALTER TABLE users ADD COLUMN profile_picture VARCHAR DEFAULT NULL")
            # SQLite uses generic types mostly, VARCHAR is fine.
            # Postgres supports VARCHAR/TEXT.
            
            connection.execute(alter_query)
            connection.commit()
            print("✅ Column 'profile_picture' added successfully.")
            
        except Exception as e:
            if "duplicate column" in str(e) or "already exists" in str(e):
                print("ℹ️ Column 'profile_picture' already exists. Skipping.")
            else:
                print(f"❌ Error adding column: {e}")

if __name__ == "__main__":
    add_profile_picture_column()
