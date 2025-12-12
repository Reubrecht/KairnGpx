
import json
import unicodedata
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app import models

class RaceImporter:
    @staticmethod
    def slugify(value):
        value = str(value)
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        value = re.sub(r'[^\w\s-]', '', value.lower())
        return re.sub(r'[-\s]+', '-', value).strip('-_')

    @staticmethod
    def import_from_json(json_content: list, db: Session, user_id: int = None) -> dict:
        """
        Imports races from a list of race dictionaries.
        Returns a summary dict of what was created.
        """
        stats = {
            "events_created": 0,
            "events_existed": 0,
            "editions_created": 0,
            "routes_created": 0,
            "errors": []
        }

        for item in json_content:
            event_name = item.get("nom")
            city = item.get("ville")
            
            if not event_name:
                continue

            try:
                # 1. Race Event
                slug = RaceImporter.slugify(event_name)
                
                event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == slug).first()
                if not event:
                    event = models.RaceEvent(
                        name=event_name,
                        slug=slug,
                        region=city 
                    )
                    db.add(event)
                    db.commit()
                    db.refresh(event)
                    stats["events_created"] += 1
                else:
                    stats["events_existed"] += 1

                # 2. Race Edition
                date_str = item.get("date_debut")
                if date_str:
                    start_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    year = start_date.year
                    
                    edition = db.query(models.RaceEdition).filter(
                        models.RaceEdition.event_id == event.id,
                        models.RaceEdition.year == year
                    ).first()
                    
                    if not edition:
                        edition = models.RaceEdition(
                            event_id=event.id,
                            year=year,
                            start_date=start_date,
                            status=models.RaceStatus.UPCOMING
                        )
                        db.add(edition)
                        db.commit()
                        db.refresh(edition)
                        stats["editions_created"] += 1
                    
                    # 3. Race Routes
                    courses = item.get("courses", [])
                    
                    # Check if routes already exist for this edition to avoid duplicates
                    # A simple check: if edition has routes, skip (or we could check one by one)
                    # For bulk import ease, we skip if ANY routes exist.
                    existing_routes_count = db.query(models.RaceRoute).filter(models.RaceRoute.edition_id == edition.id).count()
                    
                    if existing_routes_count == 0 and courses:
                        for c in courses:
                            dist = c.get("distance_km")
                            elev = c.get("denivele_m")
                            # Simple name generation
                            route_name = f"{dist}km - {elev}m+"
                            
                            new_route = models.RaceRoute(
                                edition_id=edition.id,
                                name=route_name,
                                distance_category=f"{dist}K"
                            )
                            db.add(new_route)
                            stats["routes_created"] += 1
                        db.commit()
                        
            except Exception as e:
                error_msg = f"Error processing {event_name}: {str(e)}"
                print(error_msg)
                stats["errors"].append(error_msg)

        return stats
