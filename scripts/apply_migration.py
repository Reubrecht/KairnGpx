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
            lines = f.readlines()
        
        # Remove comments and empty lines
        clean_lines = [l for l in lines if l.strip() and not l.strip().startswith("--")]
        sql_statements = "".join(clean_lines)
        
        statements = sql_statements.split(';')
        for statement in statements:
            if statement.strip():
                print(f"Executing: {statement.strip()[:50]}...")
                db.execute(text(statement.strip()))
        
        db.commit()
        print("Migration applied successfully.")
    except Exception as e:
        print(f"Error applying migration: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    apply_migration()
