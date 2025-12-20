import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

def run_migration():
    print("Starting manual migration...")
    with engine.connect() as connection:
        # Check if using SQLite or Postgres to adjust syntax if needed
        # SQLite doesn't support "ADD COLUMN IF NOT EXISTS" easily in one go, 
        # but SQLAlchemy text execution should handle standard ADD COLUMN.
        
        # 1. Add is_email_verified
        try:
            print("Adding column 'is_email_verified'...")
            # SQLite safe syntax (no IF NOT EXISTS usually, but let's try standard SQL)
            # Depending on DB, we might fail if exists.
            connection.execute(text("ALTER TABLE users ADD COLUMN is_email_verified BOOLEAN DEFAULT FALSE"))
            print("Column 'is_email_verified' added.")
        except Exception as e:
            print(f"Skipping 'is_email_verified' (might already exist): {e}")

        # 2. Add email_verification_token
        try:
            print("Adding column 'email_verification_token'...")
            connection.execute(text("ALTER TABLE users ADD COLUMN email_verification_token VARCHAR"))
            print("Column 'email_verification_token' added.")
        except Exception as e:
            print(f"Skipping 'email_verification_token' (might already exist): {e}")
            
        connection.commit()
    print("Migration finished.")

if __name__ == "__main__":
    run_migration()
