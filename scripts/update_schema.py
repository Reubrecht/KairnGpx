import sys
import os

# Add project root to path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from sqlalchemy import create_engine, text
from app.database import SQLALCHEMY_DATABASE_URL
import sys

def update_schema():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    print("🔄 Attempting to update database schema...")
    
    # Check if 'role' column exists in 'users' table
    # This is a bit manual for SQLite, easier to just try adding it and ignore error
    
    with engine.connect() as conn:
        try:
            # 1. Add role column
            # Note: SQLite ALER TABLE doesn't support complex types like ENUM easily in ADD COLUMN, 
            # but SQLAlchemy stores Enums as VARCHAR by default (unless native enum supported by DB).
            # We simply add it as VARCHAR(10) or TEXT with a default.
            print("  Adding 'role' column to 'users' table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user'"))
            conn.commit()
            print("  ✅ Column 'role' added successfully.")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("  ℹ️ Column 'role' already exists. Skipping.")
            else:
                print(f"  ⚠️ Warning creating 'role' column: {e}")

        # Note: 'is_admin' is already there? Yes.
        
        # We might also need to ensure Race tables exist...
        # But allow imports.py or main.py startup to create them?
        # Actually main.py typically calls Base.metadata.create_all() at startup, 
        # so NEW tables (RaceEvent, etc.) will be created automatically.
        # Only modifications to EXISTING tables (Users) need this manual step.
        
    print("✅ Schema update check complete.")

if __name__ == "__main__":
    update_schema()
