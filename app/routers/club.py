from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models
from ..dependencies import get_db, get_current_user, get_current_user_optional, templates

router = APIRouter(prefix="/club", tags=["club"])

@router.get("", response_class=HTMLResponse)
async def club_dashboard(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login?next=/club")
    
    # If user has no club, specific view or redirect?
    # Let's show a "Join/Create Club" view within the same template or a specific state
    if not user.club_affiliation:
        return templates.TemplateResponse("club.html", {
            "request": request, 
            "user": user,
            "has_club": False
        })
        
    # User has a club
    club_name = user.club_affiliation
    
    # Get Members
    members = db.query(models.User).filter(models.User.club_affiliation == club_name).all()
    
    # Get Stats
    total_km = 0
    total_elev = 0
    member_count = len(members)
    
    # Get Recent Tracks from Club Members
    # We join Track -> User and filter by User.club_affiliation
    recent_tracks = db.query(models.Track).join(models.User).filter(
        models.User.club_affiliation == club_name,
        models.Track.visibility == models.Visibility.PUBLIC # Only public tracks in club feed? Or all? Usually Club = Trusted, but let's stick to Public for safety unless specific Club logic exists.
    ).order_by(models.Track.created_at.desc()).limit(20).all()
    
    # Calc totals from members (approximate or explicit query)
    # Simple query for totals
    # Aggregate all tracks from these users
    # This might be heavy if many users, but fine for MVP
    member_ids = [m.id for m in members]
    
    stats_query = db.query(
        func.sum(models.Track.distance_km).label("total_dist"),
        func.sum(models.Track.elevation_gain).label("total_elev")
    ).filter(models.Track.user_id.in_(member_ids)).first()
    
    if stats_query.total_dist:
        total_km = stats_query.total_dist
    if stats_query.total_elev:
        total_elev = stats_query.total_elev
        
    return templates.TemplateResponse("club.html", {
        "request": request,
        "user": user,
        "has_club": True,
        "club_name": club_name,
        "members": members,
        "member_count": member_count,
        "recent_tracks": recent_tracks,
        "total_km": total_km,
        "total_elev": total_elev
    })

@router.post("/join")
async def join_club(
    request: Request, 
    club_name: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    
    if not club_name or len(club_name.strip()) < 3:
        # Error handling via query param for simplicity in this stack
        return RedirectResponse(url="/club?error=Nom du club invalide", status_code=status.HTTP_303_SEE_OTHER)
        
    user.club_affiliation = club_name.strip()
    db.commit()
    
    return RedirectResponse(url="/club", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/leave")
async def leave_club(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    user.club_affiliation = None
    db.commit()
    return RedirectResponse(url="/club", status_code=status.HTTP_303_SEE_OTHER)
