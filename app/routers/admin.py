import os
import json
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import get_db, get_current_user, get_current_admin, get_current_super_admin, templates
from ..utils import calculate_file_hash, get_location_info
from ..services.prediction_config_manager import PredictionConfigManager
from ..services.import_service import process_race_import
from ..services.analytics import GpxAnalytics
from ..services.ai_analyzer import AiAnalyzer

router = APIRouter()

# Helper to get model by name
def get_model_by_name(name: str):
    name = name.lower()
    mapping = {
        "user": models.User,
        "track": models.Track,
        "raceevent": models.RaceEvent,
        "raceedition": models.RaceEdition,
        "raceroute": models.RaceRoute,
        "eventrequest": models.EventRequest,
        "trackrequest": models.TrackRequest,
        "oauthconnection": models.OAuthConnection,
        "media": models.Media
    }
    return mapping.get(name)

@router.post("/api/admin/normalize_event")
async def api_normalize_event(
    name: str = Form(...),
    region: str = Form(None),
    website: str = Form(None),
    description: str = Form(None),
    current_user: models.User = Depends(get_current_super_admin)
):
    analyzer = AiAnalyzer()
    normalized = analyzer.normalize_event(name, region, website, description)
    return normalized

# --- SUPER ADMIN : DB TOOL ---

@router.get("/api/admin/db/tables")
async def api_get_db_tables(current_user: models.User = Depends(get_current_super_admin)):
    """Return list of available table names for the admin inspector"""
    return [
        "User", "Track", "RaceEvent", "RaceEdition", "RaceRoute", 
        "EventRequest", "TrackRequest", "OAuthConnection", "Media"
    ]

@router.get("/api/admin/db/table/{table_name}")
async def api_get_table_data(
    table_name: str, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    """Return raw data for a specific table"""
    model = get_model_by_name(table_name)
    if not model:
         raise HTTPException(status_code=404, detail="Table not found")
    
    # Fetch data
    items = db.query(model).limit(limit).all()
    
    # Serialize simplistic data
    # (Complex relationships might render as strings or need specific handling, 
    # but for a 'light' tool, returning dicts is usually fine with FastAPI's encoder,
    # though circular refs in relationships could be an issue if we returned ORM objects directly.
    # We should return a list of dicts safely.)
    
    results = []
    for item in items:
        # inspect columns
        data = {}
        for col in item.__table__.columns:
            val = getattr(item, col.name)
            # data[col.name] = str(val) if val is not None else None
            # Actually FastAPI handles most basic types. 
            # We might want to handle Enum or UUID to string explicitly if needed, but let's try direct.
            data[col.name] = val
        results.append(data)
        
    return {"data": results, "columns": [c.name for c in model.__table__.columns]}

@router.delete("/api/admin/db/table/{table_name}/{id}")
async def api_delete_table_row(
    table_name: str, 
    id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    model = get_model_by_name(table_name)
    if not model:
         raise HTTPException(status_code=404, detail="Table not found")
         
    item = db.query(model).filter(model.id == id).first()
    if item:
        db.delete(item)
        db.commit()
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Item not found")

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user.is_admin:
        return RedirectResponse(url="/", status_code=303)
        
    all_users = db.query(models.User).all()
    all_tracks = db.query(models.Track).order_by(models.Track.created_at.desc()).all()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "users": all_users,
        "tracks": all_tracks
    })

@router.get("/superadmin", response_class=HTMLResponse)
async def super_admin_dashboard(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_super_admin)):
    
    events = db.query(models.RaceEvent).all()
    users = db.query(models.User).all()
    pending_tracks = db.query(models.Track).filter(models.Track.verification_status == models.VerificationStatus.PENDING).all()
    event_requests = db.query(models.EventRequest).filter(models.EventRequest.status == "PENDING").all()
    pending_count = len(pending_tracks) + len(event_requests)
    
    # Serialize pending tracks for map preview (similar to explore page)
    # We only need basic info + path if available (or endpoints if path is heavy/missing)
    # For simplicity/performance in admin, we might just load file path or check if we have geometry columns.
    # Logic adapted from 'explore' page map approach
    pending_tracks_data = []
    
    for t in pending_tracks:
        # Basic serialization
        t_data = {
            "id": t.id,
            "title": t.title,
            "distance_km": t.distance_km,
            "elevation_gain": t.elevation_gain,
            "geojson_url": f"/api/tracks/{t.id}/geojson" # Assuming this endpoint exists or similar
        }
        pending_tracks_data.append(t_data)
        
    return templates.TemplateResponse("super_admin.html", {
        "request": request, 
        "user": current_user,
        "events": events,
        "users": users,
        "pending_count": pending_count,
        "pending_tracks": pending_tracks,
        "pending_tracks_json": json.dumps(pending_tracks_data), # JSON for JS
        "event_requests": event_requests,
        "prediction_config": PredictionConfigManager.get_config(),
        "prediction_config_json": json.dumps(PredictionConfigManager.get_config()),
        "user_has_custom_config": bool(current_user.prediction_config)
    })

# --- SUPER ADMIN : EVENTS ---

@router.get("/superadmin/event/new", response_class=HTMLResponse)
async def new_event_page(
    request: Request, 
    request_id: Optional[int] = None,
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_super_admin)
):
    # If request_id is provided, pre-fill data
    req_name = ""
    req_slug = ""
    req_website = ""
    
    if request_id:
        req = db.query(models.EventRequest).filter(models.EventRequest.id == request_id).first()
        if req:
            req_name = req.event_name
            # Simplified slugify logic for pre-fill
            import re
            import unicodedata
            
            s = unicodedata.normalize('NFKD', req.event_name).encode('ascii', 'ignore').decode('utf-8')
            s = re.sub(r'[^\w\s-]', '', s).strip().lower()
            req_slug = re.sub(r'[-\s]+', '-', s)
            
            req_website = req.website

    return templates.TemplateResponse("event_submit.html", {
        "request": request,
        "event": None,
        "request_id": request_id,
        "request_name": req_name,
        "request_slug": req_slug,
        "request_website": req_website
    })

@router.get("/superadmin/event/{event_id}/edit", response_class=HTMLResponse)
async def edit_event_page(
    event_id: int, 
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_super_admin)
):
    event = db.query(models.RaceEvent).filter(models.RaceEvent.id == event_id).first()
    if not event:
         raise HTTPException(status_code=404, detail="Event not found")
         
    return templates.TemplateResponse("event_submit.html", {
        "request": request,
        "event": event
    })

@router.post("/superadmin/events")
async def create_event(
    name: str = Form(...),
    slug: str = Form(...),
    website: str = Form(None),
    description: str = Form(None),
    region: str = Form(None),
    city: str = Form(None),
    country: str = Form(None),
    circuit: str = Form(None),
    request_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    try:
        existing_event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == slug).first()
        if existing_event:
             # Event exists, redirect to it instead of crashing
             return RedirectResponse(url=f"/superadmin#event-{existing_event.id}", status_code=303)

        new_event = models.RaceEvent(
            name=name, slug=slug, website=website, description=description,
            region=region, circuit=circuit, city=city, country=country
        )
        db.add(new_event)
        
        # If created from a request, mark it as approved
        if request_id and request_id.strip():
            try:
                rid = int(request_id)
                req = db.query(models.EventRequest).filter(models.EventRequest.id == rid).first()
                if req:
                    req.status = "APPROVED"
            except ValueError:
                pass
                
        db.commit()
    except Exception as e:
        print(f"Error creating event: {e}")
        db.rollback()
    return RedirectResponse(url=f"/superadmin#event-{new_event.id}", status_code=303)

@router.post("/superadmin/events/{event_id}/update")
async def update_event(
    event_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    website: str = Form(None),
    description: str = Form(None),
    region: str = Form(None),
    city: str = Form(None),
    country: str = Form(None),
    circuit: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    event = db.query(models.RaceEvent).filter(models.RaceEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.name = name
    event.slug = slug
    event.website = website
    event.description = description
    event.region = region
    event.city = city
    event.country = country
    event.circuit = circuit
    db.commit()
    return RedirectResponse(url=f"/superadmin#event-{event_id}", status_code=303)

@router.post("/superadmin/events/{event_id}/delete")
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    event = db.query(models.RaceEvent).filter(models.RaceEvent.id == event_id).first()
    if event:
        db.delete(event)
        db.commit()
    return RedirectResponse(url="/superadmin#events", status_code=303)

@router.post("/superadmin/event/{event_id}/add_edition")
async def add_edition(
    event_id: int,
    year: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    existing = db.query(models.RaceEdition).filter_by(event_id=event_id, year=year).first()
    if not existing:
        new_edition = models.RaceEdition(event_id=event_id, year=year)
        db.add(new_edition)
        db.commit()
    return RedirectResponse(url=f"/superadmin#event-{event_id}", status_code=303)

@router.get("/superadmin/edition/{edition_id}", response_class=HTMLResponse)
async def edition_manager(edition_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_super_admin)):
    edition = db.query(models.RaceEdition).filter(models.RaceEdition.id == edition_id).first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
        
    return templates.TemplateResponse("edition_manager.html", {
        "request": request,
        "edition": edition
    })

@router.post("/superadmin/edition/{edition_id}/add_route")
async def add_route(
    edition_id: int,
    name: str = Form(...),
    distance_km: float = Form(0),
    elevation_gain: int = Form(0),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    # Check for duplicate route in this edition
    existing_route = db.query(models.RaceRoute).filter(
        models.RaceRoute.edition_id == edition_id, 
        models.RaceRoute.name == name
    ).first()
    
    if existing_route:
        # Avoid duplicate, just redirect
        return RedirectResponse(url=f"/superadmin#events", status_code=303)

    new_route = models.RaceRoute(
        edition_id=edition_id,
        name=name,
        distance_km=distance_km,
        elevation_gain=elevation_gain
    )
    db.add(new_route)
    db.commit()
    return RedirectResponse(url="/superadmin#events", status_code=303)

@router.post("/superadmin/routes/{route_id}/link_existing_track")
async def link_route_existing_track(
    route_id: int,
    track_input: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    route = db.query(models.RaceRoute).filter(models.RaceRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    # Parse input (ID or URL)
    track_id = None
    if track_input.isdigit():
        track_id = int(track_input)
    else:
        # Try to extract ID from URL like /track/123
        import re
        match = re.search(r'/track/(\d+)', track_input)
        if match:
            track_id = int(match.group(1))
            
    if not track_id:
         # flash error? For now just redirect
         print(f"Invalid track input: {track_input}")
         return RedirectResponse(url="/superadmin#events", status_code=303)

    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        print(f"Track {track_id} not found")
        return RedirectResponse(url="/superadmin#events", status_code=303)
        
    # Link
    route.official_track_id = track.id
    
    # Update track status to reflect official nature
    track.is_official_route = True
    track.verification_status = models.VerificationStatus.VERIFIED_HUMAN
    track.visibility = models.Visibility.PUBLIC
    track.title = f"{route.edition.event.name} {route.edition.year} - {route.name}"
    
    db.commit()
    return RedirectResponse(url="/superadmin#events", status_code=303)

@router.post("/superadmin/routes/{route_id}/link_track")
async def link_route_track(
    route_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    route = db.query(models.RaceRoute).filter(models.RaceRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    content = await file.read()
    file_hash = calculate_file_hash(content)
    
    track = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
    
    if not track:
        # Create new track
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
        city, region, country = get_location_info(start_lat, start_lon)
            
        track = models.Track(
            title=f"{route.edition.event.name} - {route.name}", 
            description=f"Trace officielle pour {route.name}",
            uploader_name=current_user.username,
            user_id=current_user.id,
            file_hash=file_hash,
            file_path=file_path,
            distance_km=metrics["distance_km"],
            elevation_gain=metrics["elevation_gain"],
            elevation_loss=metrics["elevation_loss"],
            max_altitude=metrics["max_altitude"],
            min_altitude=metrics["min_altitude"],
            start_lat=start_lat,
            start_lon=start_lon,
            location_city=city,
            location_region=region,
            location_country=country,
            is_official_route=True,
            visibility=models.Visibility.PUBLIC,
            activity_type=models.ActivityType.TRAIL_RUNNING,
            verification_status=models.VerificationStatus.VERIFIED_HUMAN
        )
        db.add(track)
        db.flush()
        
    route.official_track_id = track.id
    track.is_official_route = True 
    route.distance_km = track.distance_km
    route.elevation_gain = track.elevation_gain
    
    db.commit()
    
    return RedirectResponse(url=f"/track/{track.id}/edit", status_code=303)


# --- SUPER ADMIN : USERS ---

@router.post("/superadmin/user/{user_id}/role")
async def update_user_role(
    user_id: int,
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if u:
        try:
            role_enum = models.Role(role)
            u.role = role_enum
            if role_enum in [models.Role.ADMIN, models.Role.SUPER_ADMIN]:
                u.is_admin = True
            else:
                u.is_admin = False
            db.commit()
        except ValueError:
            pass 
    return RedirectResponse(url="/superadmin#users", status_code=303) 

@router.post("/superadmin/user/{user_id}/edit_full")
async def edit_user_full(
    user_id: int,
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(None),
    role: str = Form(...),
    utmb_index: int = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if u:
        try:
            # Update Details
            u.username = username
            u.email = email
            u.full_name = full_name
            u.utmb_index = utmb_index
            
            # Update Role
            role_enum = models.Role(role)
            u.role = role_enum
            if role_enum in [models.Role.ADMIN, models.Role.SUPER_ADMIN]:
                u.is_admin = True
            else:
                u.is_admin = False
                
            db.commit()
        except ValueError:
            pass # Invalid role
    return RedirectResponse(url="/superadmin#users", status_code=303)

@router.post("/superadmin/user/{user_id}/toggle_premium")
async def toggle_premium_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if u:
        u.is_premium = not u.is_premium
        db.commit()
    return RedirectResponse(url="/superadmin#users", status_code=303)

@router.post("/superadmin/user/{user_id}/delete")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if u:
        if u.id == current_user.id:
             pass 
        else:
            db.query(models.Track).filter(models.Track.user_id == u.id).delete()
            db.delete(u)
            db.commit()
    return RedirectResponse(url="/superadmin#users", status_code=303)


# --- SUPER ADMIN : MODERATION ---

@router.post("/superadmin/track/{track_id}/verify")
async def verify_track_admin(track_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_super_admin)):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if track:
        track.verification_status = models.VerificationStatus.VERIFIED_HUMAN
        track.visibility = models.Visibility.PUBLIC
        db.commit()
    return RedirectResponse(url="/superadmin#moderation", status_code=303)

@router.post("/superadmin/track/{track_id}/reject")
async def reject_track_admin(
    track_id: int, 
    reason: str = Form(None), 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_super_admin)
):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if track:
        db.delete(track)
        db.commit()
    return RedirectResponse(url="/superadmin#moderation", status_code=303)

@router.post("/superadmin/track/{track_id}/link_route")
async def link_track_to_route(
    track_id: int,
    route_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    route = db.query(models.RaceRoute).filter(models.RaceRoute.id == route_id).first()
    
    if track and route:
        track.is_official_route = True
        track.verification_status = models.VerificationStatus.VERIFIED
        track.visibility = models.Visibility.PUBLIC
        track.title = f"{route.name} - Official" 
        
        route.official_track_id = track.id
        db.commit()
        
    return RedirectResponse(url="/superadmin#moderation", status_code=303)

# --- PREDICTION CONFIG ---

@router.get("/api/admin/prediction_config")
async def get_prediction_config(current_user: models.User = Depends(get_current_super_admin)):
    return PredictionConfigManager.get_config()

@router.post("/api/admin/prediction_config")
async def update_prediction_config(
    request: Request,
    current_user: models.User = Depends(get_current_super_admin)
):
    form_data = await request.form()
    config = {k: float(v) for k, v in form_data.items() if v}
    PredictionConfigManager.save_config(config)
    return RedirectResponse(url="/superadmin#prediction", status_code=303)

@router.post("/api/admin/reset_personal_config")
async def reset_personal_config(
    current_user: models.User = Depends(get_current_super_admin),
    db: Session = Depends(get_db)
):
    current_user.prediction_config = None
    db.commit()
    return RedirectResponse(url="/superadmin#prediction", status_code=303)

@router.post("/superadmin/import_races")
async def import_races_json(file: UploadFile, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_super_admin)):
    content = await file.read()
    count = process_race_import(db, content)
    print(f"Imported {count} routes via API.")
    return RedirectResponse(url="/superadmin#events", status_code=303)


@router.get("/api/admin/pending_count")
async def get_pending_count(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_admin)):
    req_count = db.query(models.EventRequest).filter(models.EventRequest.status == "PENDING").count()
    track_count = db.query(models.Track).filter(models.Track.verification_status == models.VerificationStatus.PENDING).count()
    return {"count": req_count + track_count, "requests": req_count, "tracks": track_count}
