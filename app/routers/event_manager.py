import shutil
import uuid
import os
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from .. import models
from ..dependencies import get_db, get_current_user, templates
from ..services.import_service import process_race_import
from ..utils import calculate_file_hash, get_location_info
from ..services.analytics import GpxAnalytics

router = APIRouter()

# Dependency to check permissions (Mocked as any logged user for now, or admin)
def get_manager_user(user: models.User = Depends(get_current_user)):
    # Uncomment to restrict to Admin/Moderator
    # if user.role not in [models.Role.ADMIN, models.Role.SUPER_ADMIN, models.Role.MODERATOR]:
    #     raise HTTPException(status_code=403, detail="Not authorized")
    return user

@router.get("/manage/events", response_class=HTMLResponse)
async def list_events(
    request: Request, 
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    query = db.query(models.RaceEvent)
    
    if q:
        search = f"%{q}%"
        query = query.filter(
            or_(
                models.RaceEvent.name.ilike(search),
                models.RaceEvent.region.ilike(search),
                models.RaceEvent.slug.ilike(search),
                models.RaceEvent.circuit.ilike(search)
            )
        )
    
    events = query.order_by(models.RaceEvent.name).all()
    
    return templates.TemplateResponse("manager/event_search.html", {
        "request": request,
        "events": events,
        "query": q,
        "user": user
    })

@router.get("/manage/events/new", response_class=HTMLResponse)
async def new_event_form(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    return templates.TemplateResponse("manager/event_form.html", {
        "request": request,
        "event": None,
        "user": user
    })

@router.post("/manage/events")
async def create_event(
    name: str = Form(...),
    slug: str = Form(...),
    city: str = Form(None),
    region: str = Form(None),
    country: str = Form(None),
    circuit: str = Form(None),
    website: str = Form(None),
    description: str = Form(None),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    # Check duplicate slug
    if db.query(models.RaceEvent).filter(models.RaceEvent.slug == slug).first():
        # Simple error handling
        raise HTTPException(status_code=400, detail="Slug already exists")

    new_event = models.RaceEvent(
        name=name,
        slug=slug,
        city=city,
        region=region,
        country=country,
        circuit=circuit,
        website=website,
        description=description
    )
    
    if image_file and image_file.filename:
        upload_dir = Path("app/media/events")
        upload_dir.mkdir(parents=True, exist_ok=True)
        ext = image_file.filename.split('.')[-1].lower()
        filename = f"{slug}_{uuid.uuid4().hex[:6]}.{ext}"
        file_path = upload_dir / filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
        new_event.profile_picture = f"/media/events/{filename}"

    # Add owner
    new_event.owners.append(user)

    db.add(new_event)
    db.commit()
    
    return RedirectResponse(url=f"/manage/events/{new_event.id}", status_code=303)

@router.get("/manage/events/{event_id}", response_class=HTMLResponse)
async def event_dashboard(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    event = db.query(models.RaceEvent).options(
        joinedload(models.RaceEvent.editions).joinedload(models.RaceEdition.routes)
    ).filter(models.RaceEvent.id == event_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return templates.TemplateResponse("manager/event_dashboard.html", {
        "request": request,
        "event": event,
        "user": user
    })

@router.get("/manage/events/{event_id}/edit", response_class=HTMLResponse)
async def edit_event_form(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    event = db.query(models.RaceEvent).filter(models.RaceEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    return templates.TemplateResponse("manager/event_form.html", {
        "request": request,
        "event": event,
        "user": user
    })

@router.post("/manage/events/{event_id}/update")
async def update_event(
    event_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    city: str = Form(None),
    region: str = Form(None),
    country: str = Form(None),
    circuit: str = Form(None),
    website: str = Form(None),
    description: str = Form(None),
    image_file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    event = db.query(models.RaceEvent).filter(models.RaceEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    event.name = name
    event.slug = slug
    event.city = city
    event.region = region
    event.country = country
    event.circuit = circuit
    event.website = website
    event.description = description
    
    if image_file and image_file.filename:
        upload_dir = Path("app/media/events")
        upload_dir.mkdir(parents=True, exist_ok=True)
        ext = image_file.filename.split('.')[-1].lower()
        filename = f"{slug}_{uuid.uuid4().hex[:6]}.{ext}"
        file_path = upload_dir / filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image_file.file, buffer)
        event.profile_picture = f"/media/events/{filename}"
        
    db.commit()
    return RedirectResponse(url=f"/manage/events/{event_id}", status_code=303)

@router.post("/manage/events/import")
async def import_events_json(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    content = await file.read()
    try:
        count = process_race_import(db, content)
    except Exception as e:
        # Ideally flash error
        print(f"Import error: {e}")
        
    return RedirectResponse(url="/manage/events", status_code=303)

# --- Sub-resources ---

@router.post("/manage/events/{event_id}/editions")
async def add_edition(
    event_id: int,
    year: int = Form(...),
    start_date: str = Form(None), # "YYYY-MM-DD"
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    existing = db.query(models.RaceEdition).filter_by(event_id=event_id, year=year).first()
    if not existing:
        s_date = None
        if start_date:
            try:
                from datetime import datetime
                s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
            except:
                pass
                
        new_edition = models.RaceEdition(event_id=event_id, year=year, start_date=s_date)
        db.add(new_edition)
        db.commit()
        
    return RedirectResponse(url=f"/manage/events/{event_id}", status_code=303)

@router.post("/manage/editions/{edition_id}/routes")
async def add_route(
    edition_id: int,
    name: str = Form(...),
    distance_km: float = Form(0),
    elevation_gain: int = Form(0),
    distance_category: str = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    edition = db.query(models.RaceEdition).filter(models.RaceEdition.id == edition_id).first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
        
    existing = db.query(models.RaceRoute).filter_by(edition_id=edition_id, name=name).first()
    if not existing:
        route = models.RaceRoute(
            edition_id=edition_id,
            name=name,
            distance_km=distance_km,
            elevation_gain=elevation_gain,
            distance_category=distance_category
        )
        db.add(route)
        db.commit()
        
    return RedirectResponse(url=f"/manage/events/{edition.event_id}", status_code=303)

@router.post("/manage/routes/{route_id}/upload")
async def upload_route_gpx(
    route_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    route = db.query(models.RaceRoute).filter(models.RaceRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    content = await file.read()
    file_hash = calculate_file_hash(content)
    
    track = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
    
    if not track:
        # Parse and Create Track
        analytics = GpxAnalytics(content)
        metrics = analytics.calculate_metrics()
        
        if not metrics:
             raise HTTPException(status_code=400, detail="Invalid GPX")

        filename = f"{file_hash}.gpx"
        upload_dir = "app/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
            
        start_lat, start_lon = metrics["start_coords"]
        city_loc, region_loc, country_loc = get_location_info(start_lat, start_lon)
            
        track = models.Track(
            title=f"{route.edition.event.name} {route.edition.year} - {route.name}", 
            description=f"Trace officielle pour {route.name}",
            uploader_name=user.username,
            user_id=user.id,
            file_hash=file_hash,
            file_path=file_path,
            distance_km=metrics["distance_km"],
            elevation_gain=metrics["elevation_gain"],
            elevation_loss=metrics["elevation_loss"],
            max_altitude=metrics["max_altitude"],
            min_altitude=metrics["min_altitude"],
            start_lat=start_lat,
            start_lon=start_lon,
            location_city=city_loc,
            location_region=region_loc,
            location_country=country_loc,
            is_official_route=True,
            visibility=models.Visibility.PUBLIC,
            activity_type=models.ActivityType.TRAIL_RUNNING,
            verification_status=models.VerificationStatus.VERIFIED_HUMAN
        )
        db.add(track)
        db.flush() # Get ID
        
    # Link
    route.official_track_id = track.id
    # Sync metrics if empty
    if not route.distance_km:
        route.distance_km = track.distance_km
    if not route.elevation_gain:
        route.elevation_gain = track.elevation_gain
        
    db.commit()
    
    return RedirectResponse(url=f"/manage/events/{route.edition.event_id}", status_code=303)

@router.post("/manage/events/delete_batch")
async def delete_events_batch(
    event_ids: List[int] = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    try:
        # Find events
        events_to_delete = db.query(models.RaceEvent).filter(models.RaceEvent.id.in_(event_ids)).all()
        
        for event in events_to_delete:
            # 1. Unlink Tracks from all routes in this event
            for edition in event.editions:
                for route in edition.routes:
                    if route.official_track_id:
                        track = db.query(models.Track).filter(models.Track.id == route.official_track_id).first()
                        if track:
                            track.is_official_route = False
                            # Optional: revert status if needed, but keeping as is to preserve file
                            
            # 2. Delete the event (Cascades should handle children if configured, 
            # but explicit delete of children is safer if cascade not set in DB Models)
            # Models use default relationship which might set null or cascade depending on setup.
            # Let's rely on SQLAlchemy ORM cascading if relationships are set up with `cascade="all, delete"`.
            # Looking at models.py, `cascade` is not explicitly set on relationships usually defaults to strict or set null.
            # To be safe, manual deletion of children or relying on DB constraint with CASCADE.
            # Given models review, it's safer to just delete the event and let SQLAlchemy handle it if configured, 
            # or it might fail if FK constraints exist without cascade.
            # Best practice without altering models now:
            
            for edition in event.editions:
                # Delete routes first
                for route in edition.routes:
                    db.delete(route)
                db.delete(edition)
                
            db.delete(event)
            
        db.commit()
    except Exception as e:
        print(f"Batch Delete Error: {e}")
        db.rollback()
        
    return RedirectResponse(url="/manage/events", status_code=303)
