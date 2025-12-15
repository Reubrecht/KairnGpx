import sys
import os
from sqlalchemy import text

# Add parent directory to path to import app modules
sys.path.append(os.getcwd())

from app.database import SessionLocal

def apply_migration():
    print("Applying migration...")
    db = SessionLocal()
    try:
        with open("migrations/add_location_fields.sql", "r") as f:
            sql_statements = f.read()
        
        # Split by semicolon if needed, but text() often handles scripts depending on driver
        # For simplicity, let's assume psycopg2 handles the block or we split
        
        # Simple split by ';' for safety if driver doesn't support multiple result sets in one go
        statements = sql_statements.split(';')
        for statement in statements:
            if statement.strip():
                db.execute(text(statement))
        
        db.commit()
        print("Migration applied successfully.")
    except Exception as e:
        print(f"Error applying migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    apply_migration()
