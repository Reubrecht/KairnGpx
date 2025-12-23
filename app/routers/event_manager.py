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

# Dependency to check permissions
def get_manager_user(user: models.User = Depends(get_current_user)):
    # Restrict to Admin and Super Admin
    if user.role not in [models.Role.ADMIN, models.Role.SUPER_ADMIN]:
        # Also check legacy flag just in case
        if not user.is_admin:
             raise HTTPException(status_code=403, detail="Not authorized")
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

@router.get("/manage/events/quick-create", response_class=HTMLResponse)
async def quick_create_form(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    return templates.TemplateResponse("manager/event_quick_create.html", {
        "request": request,
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
        from ..services.image_service import ImageService
        upload_dir = Path("app/media/events")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        content = await image_file.read()
        # Events usually need wider aspect ratio or flexible, max 1600 width is good for banners
        new_filename = ImageService.process_image(
            content, 
            upload_dir, 
            filename_prefix=f"banner_{slug}",
            max_width=1600,
            max_height=1200
        )
        new_event.profile_picture = f"/media/events/{new_filename}"

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

    from datetime import datetime as dt
    now_date = dt.now().date()

    return templates.TemplateResponse("manager/event_dashboard.html", {
        "request": request,
        "event": event,
        "user": user,
        "now_date": now_date
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
        # Process new image
        from ..services.image_service import ImageService
        upload_dir = Path("app/media/events")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        content = await image_file.read()
        new_filename = ImageService.process_image(
            content, 
            upload_dir, 
            filename_prefix=f"banner_{event.slug}",
            max_width=1600,
            max_height=1200
        )
        
        # Remove old image if strictly needed, but might be safer to keep for history or cache issues
        # For now, just update pointer
        event.profile_picture = f"/media/events/{new_filename}"
        
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
                            
            # 2. Delete children manually for safety
            for edition in event.editions:
                for route in edition.routes:
                    db.delete(route)
                db.delete(edition)
                
            db.delete(event)
            
        db.commit()
    except Exception as e:
        print(f"Batch Delete Error: {e}")
        db.rollback()
        
    return RedirectResponse(url="/manage/events", status_code=303)

@router.post("/manage/editions/{edition_id}/duplicate")
async def duplicate_edition(
    edition_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    """
    Duplicate an edition structure to the next year.
    Copies all routes (without linked tracks) to the new edition.
    """
    edition = db.query(models.RaceEdition).filter(models.RaceEdition.id == edition_id).first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
        
    new_year = edition.year + 1
    
    # Check if exists
    if db.query(models.RaceEdition).filter_by(event_id=edition.event_id, year=new_year).first():
        # Ideally flash message: already exists
        return RedirectResponse(url=f"/manage/events/{edition.event_id}", status_code=303)

    # Create new edition
    new_start = None
    if edition.start_date:
        try:
            # Simple heuristic: add 365 days? Or just leave null? 
            # User request: "dupliqué un evenement vers l'edition suivante"
            # Let's keep dates empty to encourage setting them correct
            pass 
        except:
            pass
            
    new_edition = models.RaceEdition(
        event_id=edition.event_id,
        year=new_year,
        status=models.RaceStatus.UPCOMING,
        start_date=None, # Reset date
        end_date=None
    )
    db.add(new_edition)
    db.flush() # Get ID
    
    # Copy routes
    for route in edition.routes:
        new_route = models.RaceRoute(
            edition_id=new_edition.id,
            name=route.name,
            distance_km=route.distance_km,
            elevation_gain=route.elevation_gain,
            distance_category=route.distance_category,
            official_track_id=None, # Do not link track by default (safer)
            results_url=None
        )
        db.add(new_route)
        
    db.commit()
    
    return RedirectResponse(url=f"/manage/events/{edition.event_id}", status_code=303)


@router.post("/manage/routes/{route_id}/link_existing")
async def link_existing_track(
    route_id: int,
    track_id: int = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    route = db.query(models.RaceRoute).filter(models.RaceRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
        
    # Link
    route.official_track_id = track.id
    track.is_official_route = True
    
    # Sync info if empty
    if not route.distance_km:
        route.distance_km = track.distance_km
    if not route.elevation_gain:
        route.elevation_gain = track.elevation_gain
        
    db.commit()
    return RedirectResponse(url=f"/manage/events/{route.edition.event_id}", status_code=303)

@router.get("/api/manage/tracks_search")
async def search_tracks_api(
    q: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    """Search tracks by title/id for the linker"""
    if not q:
        return []
        
    query = db.query(models.Track).filter(models.Track.title.ilike(f"%{q}%"))
    results = query.limit(20).all()
    
    return [
        {"id": t.id, "title": t.title, "distance": t.distance_km, "elevation": t.elevation_gain, "uploader": t.uploader_name}
        for t in results
    ]

@router.post("/manage/unified/create")
async def create_unified_event(
    request: Request,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_manager_user)
):
    """
    Unified endpoint to create Event + Edition + Multiple Routes + Tracks in one go.
    Supports optional GPX files and Event images.
    """
    from ..services.unified_event_service import UnifiedEventService
    from ..services.image_service import ImageService
    from ..utils import slugify
    
    form = await request.form()
    
    event_name = form.get("event_name")
    try:
        year = int(form.get("year"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Année invalide")

    banner_file = form.get("banner_file")
    profile_file = form.get("profile_file")

    if not event_name:
        raise HTTPException(status_code=400, detail="Nom de l'événement requis")

    service = UnifiedEventService(db, user)
    created_event = None

    # Iterate over potential routes (index 0 to N)
    i = 0
    routes_processed = 0
    
    try:
        while True:
            r_name_key = f"route_name_{i}"
            if r_name_key not in form:
                break
                
            r_name = form.get(r_name_key)
            if r_name: 
                dist_cat = form.get(f"distance_category_{i}")
                gpx_item = form.get(f"route_file_{i}")
                
                gpx_content = None
                if isinstance(gpx_item, UploadFile) and gpx_item.filename:
                    gpx_content = await gpx_item.read()
                
                result = await service.create_event_hierarchy(
                    event_name=event_name,
                    year=year,
                    route_name=r_name,
                    gpx_content=gpx_content,
                    distance_category=dist_cat
                )
                created_event = result["event"]
                routes_processed += 1
            
            i += 1
            
        # Support Event creation even without routes
        if routes_processed == 0 and not created_event:
             slug = slugify(event_name)
             created_event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == slug).first()
             if not created_event:
                created_event = models.RaceEvent(name=event_name, slug=slug)
                created_event.owners.append(user)
                db.add(created_event)
                db.flush()
             
             # Create Edition
             edition = db.query(models.RaceEdition).filter_by(event_id=created_event.id, year=year).first()
             if not edition:
                edition = models.RaceEdition(event_id=created_event.id, year=year, status=models.RaceStatus.UPCOMING)
                db.add(edition)

        # Handle Images
        if created_event:
            upload_dir = Path("app/media/events")
            upload_dir.mkdir(parents=True, exist_ok=True)

            # Banner (Header) -> mapped to profile_picture
            if isinstance(banner_file, UploadFile) and banner_file.filename:
                content = await banner_file.read()
                new_filename = ImageService.process_image(
                    content, upload_dir, 
                    filename_prefix=f"banner_{created_event.slug}",
                    max_width=1600, max_height=1200
                )
                created_event.profile_picture = f"/media/events/{new_filename}" 
                db.add(created_event)
            
            # Profile Photo -> Ideally another field, skipping for now as per schema limits

        db.commit()
        return RedirectResponse(
            url=f"/manage/events/{created_event.id}", 
            status_code=status.HTTP_303_SEE_OTHER
        )

    except Exception as e:
        print(f"Unified Create Error: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur: {str(e)}")
