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
from ..services.prediction_config_manager import PredictionConfigManager, DEFAULT_CONFIG

router = APIRouter()

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    tracks = db.query(models.Track).filter(models.Track.user_id == user.id).order_by(models.Track.created_at.desc()).all()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "tracks": tracks
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
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    
    # Handle Profile Picture
    if profile_picture and profile_picture.filename:
        try:
            # Create profiles dir
            upload_dir = Path("app/media/profiles")
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            # Simple naming strategy: user_id.jpg (or original extension)
            # To avoid caching issues, we might append timestamp but overwrite is simpler for storage
            ext = profile_picture.filename.split('.')[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                # validation could go here
                pass
                
            filename = f"{user.id}.{ext}"
            file_path = upload_dir / filename
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(profile_picture.file, buffer)
                
            # Update DB with web path
            user.profile_picture = f"/media/profiles/{filename}"
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
        "defaults": DEFAULT_CONFIG
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
