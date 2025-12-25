import os
from typing import Optional
from typing import Optional
import json
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, Request, Form, status, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import get_db, get_current_user, templates
from ..services.prediction_config_manager import PredictionConfigManager, DEFAULT_CONFIG, PRESETS

router = APIRouter()

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    tracks = db.query(models.Track).filter(models.Track.user_id == user.id).order_by(models.Track.created_at.desc()).all()
    strategies = db.query(models.RaceStrategy).filter(models.RaceStrategy.user_id == user.id).order_by(models.RaceStrategy.created_at.desc()).all()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "tracks": tracks,
        "strategies": strategies
    })

@router.post("/profile")
async def update_profile(
    request: Request,
    full_name: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    club_affiliation: Optional[str] = Form(None),
    strava_url: Optional[str] = Form(None),
    website: Optional[str] = Form(None),
    itra_score: Optional[int] = Form(None),
    utmb_index: Optional[int] = Form(None),
    betrail_score: Optional[float] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    
    # New Location Fields
    location_city: Optional[str] = Form(None),
    location_region: Optional[str] = Form(None),
    location_country: Optional[str] = Form(None),
    location_lat: Optional[float] = Form(None),
    location_lon: Optional[float] = Form(None),

    # Notifications
    notify_newsletter: Optional[bool] = Form(False),
    notify_messages: Optional[bool] = Form(False),
    notify_tracks: Optional[bool] = Form(False),
    
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    
    # Handle Profile Picture
    if profile_picture and profile_picture.filename:
        try:
            from ..services.image_service import ImageService
            
            # Create profiles dir
            upload_dir = Path("app/media/profiles")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            content = await profile_picture.read()
            new_filename = ImageService.process_profile_picture(content, upload_dir, user.username)

            # Update DB with web path
            user.profile_picture = f"/media/profiles/{new_filename}"
        except Exception as e:
            print(f"Error uploading profile picture: {e}")
            # Continue updating other fields
    
    user.full_name = full_name
    user.bio = bio
    user.location = location
    user.club_affiliation = club_affiliation
    user.strava_url = strava_url
    user.website = website
    user.itra_score = itra_score
    user.utmb_index = utmb_index
    user.betrail_score = betrail_score
    
    # Update granular location
    if location_lat is not None: user.location_lat = location_lat
    if location_lon is not None: user.location_lon = location_lon
    if location_city is not None: user.location_city = location_city
    if location_region is not None: user.location_region = location_region
    if location_region is not None: user.location_region = location_region
    if location_country is not None: user.location_country = location_country

    # Update Notifications
    # We construct the JSON object. Since HTML checkboxes only send value if checked,
    # and we default to False in args, this works for unchecking.
    # Note: If form didn't include them at all (e.g. from a different form), we might overwrite with False.
    # But this is the main profile form.
    user.notification_preferences = {
        "newsletter": notify_newsletter,
        "messages": notify_messages,
        "tracks": notify_tracks
    }
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "notification_preferences")
    
    db.commit()
    
    return RedirectResponse(url="/profile", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/profile/upgrade")
async def upgrade_premium(
    request: Request,
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    required_code = os.getenv("INVITATION_CODE")
    if not required_code:
        required_code = "Kairn2025!"
        
    if code.strip() == required_code.strip():
        user.is_premium = True
        db.commit()
        return RedirectResponse(url="/profile?success=Premium Activated", status_code=303)
    else:
        return RedirectResponse(url="/profile?error=Invalid Code", status_code=303)

@router.post("/request_event")
async def request_event(
    request: Request,
    event_name: str = Form(...),
    year: int = Form(None),
    website: str = Form(None),
    comment: str = Form(None),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    
    new_req = models.EventRequest(
        user_id=user.id,
        event_name=event_name,
        year=year,
        website=website,
        comment=comment
    )
    db.add(new_req)
    db.commit()
    
    return RedirectResponse(request.headers.get("referer") or "/", status_code=303)

@router.get("/profile/prediction", response_class=HTMLResponse)
async def prediction_settings(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user.is_premium:
        return RedirectResponse(url="/profile", status_code=303)
        
    # Start with global default
    config = PredictionConfigManager.get_config()
    
    # If user has custom config, override
    if user.prediction_config:
        config.update(user.prediction_config)
        
    return templates.TemplateResponse("prediction_settings.html", {
        "request": request,
        "user": user,
        "config": config,
        "user": user,
        "config": config,
        "defaults": DEFAULT_CONFIG,
        "presets": PRESETS
    })

@router.post("/profile/prediction")
async def update_prediction_settings(
    request: Request,
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user.is_premium:
        raise HTTPException(status_code=403, detail="Premium only")
        
    form = await request.form()
    
    # Extract keys from defaults to know what to look for
    new_config = {}
    for key, default_val in DEFAULT_CONFIG.items():
        if key in form:
            try:
                # Convert to float/int based on default type
                if isinstance(default_val, int):
                    new_config[key] = int(form[key])
                else:
                    new_config[key] = float(form[key])
            except ValueError:
                new_config[key] = default_val # Fallback
                
    # Save to user
    # SQLAlchemy JSON type handling: reassign to trigger detection or use flag
    user.prediction_config = new_config
    
    # Force flag modified if needed (for some sqlalchemy versions with JSON)
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "prediction_config")
    
    db.commit()
    
    return RedirectResponse(url="/profile/prediction?success=Saved", status_code=303)

@router.post("/profile/prediction/reset")
async def reset_prediction_settings(
    request: Request,
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    user.prediction_config = None
    db.commit()
    return RedirectResponse(url="/profile/prediction?success=Reset", status_code=303)

@router.post("/profile/prediction/apply_preset")
async def apply_prediction_preset(
    request: Request,
    preset: str = Form(...),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user.is_premium:
        raise HTTPException(status_code=403, detail="Premium only")
        
    if preset not in PRESETS:
        return RedirectResponse(url="/profile/prediction?error=Unknown Preset", status_code=303)

    # Apply the preset config
    # We copy it to ensure we don't modify the global constant if we were mutable (dicts are reference)
    import copy
    new_conf = copy.deepcopy(PRESETS[preset]["config"])
    
    user.prediction_config = new_conf
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(user, "prediction_config")
    
    db.commit()
    
    return RedirectResponse(url=f"/profile/prediction?success=Preset {PRESETS[preset]['name']} Applied", status_code=303)


@router.get("/user/{username}", response_class=HTMLResponse)
async def public_profile(
    username: str, 
    request: Request, 
    db: Session = Depends(get_db)
):
    target_user = db.query(models.User).filter(models.User.username == username).first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Get public tracks
    # Logic: Public visibility AND verified? Or just public?
    # Usually public profile shows whatever user set to 'public'.
    # Filter by user_id AND visibility=PUBLIC
    
    public_tracks = db.query(models.Track).filter(
        models.Track.user_id == target_user.id,
        models.Track.visibility == models.Visibility.PUBLIC
    ).order_by(models.Track.created_at.desc()).all()

    # Calculate Totals
    total_km = sum(t.distance_km for t in public_tracks if t.distance_km)
    total_elev = sum(t.elevation_gain for t in public_tracks if t.elevation_gain)

    # Fetch recorded executions 
    # Logic: executions are linked to user_id. We might want only those on public tracks? 
    # Or all executions? Let's show all executions for now as it's the user's log.
    executions = db.query(models.TrackExecution).filter(
        models.TrackExecution.user_id == target_user.id
    ).order_by(models.TrackExecution.execution_date.desc()).all()
    
    from ..dependencies import get_current_user_optional
    viewer = await get_current_user_optional(request, db)
    
    return templates.TemplateResponse("user_public_profile.html", {
        "request": request,
        "user": target_user, # The profile owner
        "viewer": viewer, # The person watching (can be None)
        "tracks": public_tracks,
        "total_km": total_km,
        "total_elev": total_elev,
        "executions": executions,
        "execution_count": len(executions)
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    return templates.TemplateResponse("settings.html", {"request": request, "user": user})
