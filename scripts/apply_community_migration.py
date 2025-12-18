import sys
import os
from sqlalchemy import text

# Add parent directory to path to import app modules
sys.path.append(os.getcwd())

from app.database import SessionLocal

def apply_migration():
    print("Applying Community Tables Migration...")
    db = SessionLocal()
    try:
        # Read the migration file
        migration_file = "migrations/create_community_tables.sql"
        if not os.path.exists(migration_file):
            print(f"Error: Migration file not found at {migration_file}")
            return

        with open(migration_file, "r") as f:
            lines = f.readlines()
        
        # Remove comments (simple check) and empty lines to get statements
        # Note: This simple parser assumes statements end with ;
        sql_statements = "".join([l for l in lines if not l.strip().startswith("--")])
        
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
