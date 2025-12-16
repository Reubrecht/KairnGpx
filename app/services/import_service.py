import json
from datetime import datetime
from slugify import slugify
from sqlalchemy.orm import Session
from app import models

def process_race_import(db: Session, content: bytes) -> int:
    """
    Parses JSON content and imports races/editions/routes into the database.
    Supports both Standard Schema and French Schema (nom/date_debut/courses).
    Returns the number of routes imported.
    """
    try:
        data = json.loads(content)
    except Exception as e:
        print(f"JSON Load Error: {e}")
        return 0

    count = 0
    for item in data:
        try:
            # 1. DETECT SCHEMA & NORMALIZE
            # Schema FR (race_fr_11.json, race_fr_66.json)
            if 'nom' in item and 'date_debut' in item:
                evt_name = item['nom']
                evt_slug = slugify(evt_name)
                
                # Parse date for year
                try:
                        d_enc = item['date_debut']
                        year = int(d_enc.split('-')[0])
                        s_date = datetime.strptime(d_enc, "%Y-%m-%d").date()
                except:
                    year = datetime.now().year + 1
                    s_date = None

                # Routes list
                raw_routes = item.get('courses', [])
                
                # Clean Event Name (Strip Year if present)
                # e.g. "UTMB 2024" -> "UTMB"
                if year and evt_name.strip().endswith(str(year)):
                    evt_name = evt_name.replace(str(year), "").strip().rstrip("-")
                    evt_slug = slugify(evt_name)

                # A. Upsert Event
                event = db.query(models.RaceEvent).filter_by(slug=evt_slug).first()
                if not event:
                    event = models.RaceEvent(
                        name=evt_name,
                        slug=evt_slug,
                        region=item.get('ville')
                    )
                    db.add(event)
                    db.commit()
                    db.refresh(event)

                # B. Upsert Edition
                edition = db.query(models.RaceEdition).filter_by(event_id=event.id, year=year).first()
                if not edition:
                    print(f"Creating Edition {year} for {evt_name}")
                    edition = models.RaceEdition(
                        event_id=event.id, 
                        year=year,
                        start_date=s_date
                    )
                    db.add(edition)
                    db.commit()
                    db.refresh(edition)

                # C. Upsert Routes
                print(f"Found {len(raw_routes)} routes for {evt_name}")
                for c in raw_routes:
                    dist = c.get('distance_km', 0)
                    elev = c.get('denivele_m', 0)
                    r_name = f"{dist}km" # Default name
                    
                    route = db.query(models.RaceRoute).filter_by(edition_id=edition.id, name=r_name).first()
                    if not route:
                        print(f"  -> Adding route {r_name}")
                        route = models.RaceRoute(
                            edition_id=edition.id,
                            name=r_name,
                            distance_km=dist,
                            elevation_gain=elev
                        )
                        db.add(route)
                        count += 1
                    # else:
                        # print(f"  -> Route {r_name} exists")
                continue # Done with this item (FR Schema)

            # Schema STANDARD
            if not item.get('name'):
                continue
                
            # Upsert Event
            slug = item.get('slug')
            if not slug:
                slug = slugify(item['name'])
                
            event = db.query(models.RaceEvent).filter_by(slug=slug).first()
            if not event:
                event = models.RaceEvent(
                    name=item['name'],
                    slug=slug,
                    website=item.get('website'),
                    description=item.get('description')
                )
                db.add(event)
                db.commit()
                db.refresh(event)
            
            # Editions
            for ed in item.get('editions', []):
                edition = db.query(models.RaceEdition).filter_by(event_id=event.id, year=ed['year']).first()
                if not edition:
                    edition = models.RaceEdition(event_id=event.id, year=ed['year'])
                    db.add(edition)
                    db.commit()
                    db.refresh(edition)
                
                # Routes
                for r in ed.get('routes', []):
                    if not r.get('name'):
                        continue
                        
                    route = db.query(models.RaceRoute).filter_by(edition_id=edition.id, name=r['name']).first()
                    if not route:
                        route = models.RaceRoute(
                            edition_id=edition.id,
                            name=r['name'],
                            distance_km=r.get('distance_km', 0),
                            elevation_gain=r.get('elevation_gain', 0)
                        )
                        db.add(route)
                        count += 1
                        
        except Exception as e:
            print(f"Skipping bad item in import: {e}")
            continue
            
    db.commit()
    return count
