
import json
import sys
import os
from datetime import datetime
import unicodedata
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add current dir to sys.path to ensure imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import models
from app.database import SQLALCHEMY_DATABASE_URL

def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and converts spaces to hyphens.
    """
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

def import_races(json_file):
    if not os.path.exists(json_file):
        print(f"❌ File not found: {json_file}")
        return

    # Setup DB
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"🏁 Found {len(data)} events to process.")

        for item in data:
            event_name = item.get("nom")
            city = item.get("ville")
            
            if not event_name:
                continue

            # 1. Race Event
            slug = slugify(event_name)
            
            # Check for duplicates
            event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == slug).first()
            if not event:
                print(f"  ✨ Creating Event: {event_name}")
                event = models.RaceEvent(
                    name=event_name,
                    slug=slug,
                    region=city # Using city as region for now
                )
                db.add(event)
                db.commit()
                db.refresh(event)
            else:
                print(f"  📍 Event exists: {event_name}")

            # 2. Race Edition
            date_str = item.get("date_debut")
            if date_str:
                try:
                    start_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    year = start_date.year
                    
                    edition = db.query(models.RaceEdition).filter(
                        models.RaceEdition.event_id == event.id,
                        models.RaceEdition.year == year
                    ).first()
                    
                    if not edition:
                        print(f"    🗓️ Adding Edition {year}")
                        edition = models.RaceEdition(
                            event_id=event.id,
                            year=year,
                            start_date=start_date,
                            status=models.RaceStatus.UPCOMING # Default
                        )
                        db.add(edition)
                        db.commit()
                        db.refresh(edition)
                    
                    # 3. Race Routes
                    courses = item.get("courses", [])
                    existing_routes = db.query(models.RaceRoute).filter(models.RaceRoute.edition_id == edition.id).count()
                    
                    if existing_routes == 0 and courses:
                        print(f"      🛣️ Adding {len(courses)} routes...")
                        for c in courses:
                            dist = c.get("distance_km")
                            elev = c.get("denivele_m")
                            route_name = f"{dist}km - {elev}m+"
                            
                            new_route = models.RaceRoute(
                                edition_id=edition.id,
                                name=route_name,
                                distance_category=f"{dist}K"
                            )
                            db.add(new_route)
                        db.commit()
                        
                except Exception as e:
                    print(f"    ❌ Error parsing date for {event_name}: {e}")

        print("\n✅ Import completed successfully!")

    except Exception as e:
        print(f"\n❌ Critical Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import_races("race_fr_66.json")
