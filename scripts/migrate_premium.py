import sys
import os

# Add project root to path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import engine
from sqlalchemy import text

def migrate():
    with engine.connect() as conn:
        try:
            # SQLite syntax to add column
            conn.execute(text("ALTER TABLE users ADD COLUMN is_premium BOOLEAN DEFAULT 0"))
            conn.commit()
            print("Transformation Complete: 'is_premium' column added.")
        except Exception as e:
            print(f"Migration notice: {e}")

if __name__ == "__main__":
    migrate()
