import sys
import os

# Add project root to path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import os
import glob
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import SQLALCHEMY_DATABASE_URL
from app.services.import_service import process_race_import

def import_all_races():
    # Setup DB
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Path to Race_json
    # Assuming script is run from root
    json_dir = os.path.join(os.getcwd(), 'Race_json')
    files = glob.glob(os.path.join(json_dir, '*.json'))
    
    print(f"Found {len(files)} JSON files in {json_dir}")
    
    total_imported = 0
    for file_path in files:
        print(f"Processing {os.path.basename(file_path)}...")
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                count = process_race_import(db, content)
                total_imported += count
                print(f"  -> Imported {count} routes.")
        except Exception as e:
            print(f"  -> ERROR: {e}")
            
    print(f"Done. Total routes imported: {total_imported}")
    db.close()

if __name__ == "__main__":
    import_all_races()
