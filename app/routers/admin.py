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

router = APIRouter()

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
    
    return templates.TemplateResponse("super_admin.html", {
        "request": request, 
        "user": current_user,
        "events": events,
        "users": users,
        "pending_count": pending_count,
        "pending_tracks": pending_tracks,
        "event_requests": event_requests,
        "prediction_config": PredictionConfigManager.get_config(),
        "prediction_config_json": json.dumps(PredictionConfigManager.get_config()),
        "user_has_custom_config": bool(current_user.prediction_config)
    })

# --- SUPER ADMIN : EVENTS ---

@router.post("/superadmin/events")
async def create_event(
    name: str = Form(...),
    slug: str = Form(...),
    website: str = Form(None),
    description: str = Form(None),
    region: str = Form(None),
    circuit: str = Form(None),
    request_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    try:
        if db.query(models.RaceEvent).filter(models.RaceEvent.slug == slug).first():
             # Basic conflict check
             pass 

        new_event = models.RaceEvent(
            name=name, slug=slug, website=website, description=description,
            region=region, circuit=circuit
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
    new_route = models.RaceRoute(
        edition_id=edition_id,
        name=name,
        distance_km=distance_km,
        elevation_gain=elevation_gain
    )
    db.add(new_route)
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
