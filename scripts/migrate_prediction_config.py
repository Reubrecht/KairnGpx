import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SQLALCHEMY_DATABASE_URL

def add_prediction_config_column():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    print(f"🔌 Connecting to database...")
    with engine.connect() as connection:
        try:
            # Check if column exists
            print("🔍 Checking if 'prediction_config' column exists...")
            # This query works for PostgreSQL. For SQLite it might differ, but let's try a generic approach or specific checks.
            # Simpler: just try to add it and catch error if strictly needed, but let's be cleaner.
            
            # For PostgreSQL/SQLite compatibility, pure SQL execution is best here for a simple column add.
            
            # 1. Add Column
            print("📦 Adding 'prediction_config' column to 'users' table...")
            # SQLite doesn't support "IF NOT EXISTS" in ADD COLUMN well in older versions, but Postgres does.
            # We'll use a try/except block which is safer across dialects for simple migrations without Alembic.
            
            alter_query = text("ALTER TABLE users ADD COLUMN prediction_config JSON DEFAULT NULL")
            if "sqlite" in SQLALCHEMY_DATABASE_URL:
                 alter_query = text("ALTER TABLE users ADD COLUMN prediction_config JSON")

            connection.execute(alter_query)
            connection.commit()
            print("✅ Column 'prediction_config' added successfully.")
            
        except Exception as e:
            if "duplicate column" in str(e) or "already exists" in str(e):
                print("ℹ️ Column 'prediction_config' already exists. Skipping.")
            else:
                print(f"❌ Error adding column: {e}")
                # For SQLite, if it fails, it might be due to syntax.
                # In SQLite 'JSON' type is just valid, mapped to TEXT usually.

if __name__ == "__main__":
    add_prediction_config_column()
