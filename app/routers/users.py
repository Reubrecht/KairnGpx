import os
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import get_db, get_current_user, templates

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
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    
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
