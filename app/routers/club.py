from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from .. import models
from ..dependencies import get_db, get_current_user, get_current_user_optional, templates

router = APIRouter(prefix="/club", tags=["club"])

@router.get("", response_class=HTMLResponse)
async def club_dashboard(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    if not user:
        return RedirectResponse(url="/login?next=/club")
    
    # --- MIGRATION LOGIC (On the fly) ---
    # If user has club_affiliation string BUT no club_id, try to migrate them
    if user.club_affiliation and not user.club_id:
        existing_club = db.query(models.Club).filter(models.Club.name == user.club_affiliation).first()
        if existing_club:
            user.club_id = existing_club.id
            db.commit()
        else:
            # Create it
            new_club = models.Club(
                name=user.club_affiliation, 
                owner_id=user.id, # First user becomes owner
                description="Club créé automatiquement."
            )
            db.add(new_club)
            db.commit()
            db.refresh(new_club)
            user.club_id = new_club.id
            db.commit()

    # If still no club
    if not user.club_id:
        return templates.TemplateResponse("club.html", {
            "request": request, 
            "user": user,
            "has_club": False
        })
        
    # User has a club (via ID)
    club = db.query(models.Club).filter(models.Club.id == user.club_id).first()
    if not club:
        # Fallback if DB inconsistencies
        user.club_id = None
        db.commit()
        return RedirectResponse(url="/club")

    members = db.query(models.User).filter(models.User.club_id == club.id).all()
    
    # --- FILTERS ---
    period = request.query_params.get("period", "month") # week, month, year, all
    metric = request.query_params.get("metric", "distance") # distance, elevation, time

    now = datetime.utcnow()
    start_date = None
    
    if period == "week":
        start_date = now - timedelta(days=now.weekday()) # Start of week (Monday)
    elif period == "month":
        start_date = now.replace(day=1) # Start of month
    elif period == "year":
        start_date = now.replace(month=1, day=1) # Start of year
    # else "all" -> None
    
    # --- AGGREGATION ---
    leaderboard = []
    
    for member in members:
        query = db.query(
            func.sum(models.StravaActivity.distance).label("total_dist"),
            func.sum(models.StravaActivity.total_elevation_gain).label("total_elev"),
            func.sum(models.StravaActivity.moving_time).label("total_time")
        ).filter(models.StravaActivity.user_id == member.id)
        
        if start_date:
            query = query.filter(models.StravaActivity.start_date >= start_date)
        
        # Filter for Run, Trail, Hike, Walk
        ALLOWED_TYPES = ["Run", "TrailRun", "Hike", "Walk"]
        query = query.filter(models.StravaActivity.type.in_(ALLOWED_TYPES))
            
        stats = query.first()
        
        dist = stats.total_dist if stats.total_dist else 0
        elev = stats.total_elev if stats.total_elev else 0
        time_sec = stats.total_time if stats.total_time else 0
        
        # Calculate Rank Value based on metric
        rank_val = 0
        if metric == "distance":
            rank_val = dist
        elif metric == "elevation":
            rank_val = elev
        elif metric == "time":
            rank_val = time_sec
            
        leaderboard.append({
            "user": member,
            "dist_km": round(dist / 1000, 1),
            "elev_m": round(elev, 0),
            "time_h": round(time_sec / 3600, 1),
            "rank_val": rank_val
        })
        
    # Sort Leaderboard
    leaderboard.sort(key=lambda x: x["rank_val"], reverse=True)
    
    # Assign Ranks
    for i, entry in enumerate(leaderboard):
        entry["rank"] = i + 1
    
    # Club Totals
    total_km = sum(e["dist_km"] for e in leaderboard)
    total_elev = sum(e["elev_m"] for e in leaderboard)

    # Check privileges
    is_owner = (user.id == club.owner_id)

    return templates.TemplateResponse("club.html", {
        "request": request,
        "user": user,
        "club": club,
        "has_club": True,
        "members": members,
        "member_count": len(members),
        "leaderboard": leaderboard,
        "current_period": period,
        "current_metric": metric,
        "total_km": total_km,
        "total_elev": total_elev,
        "is_owner": is_owner
    })

@router.post("/join")
async def join_club(
    request: Request, 
    club_name: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    
    if not club_name or len(club_name.strip()) < 3:
        return RedirectResponse(url="/club?error=Nom du club invalide", status_code=status.HTTP_303_SEE_OTHER)
        
    club_name_clean = club_name.strip()
    
    # Check if club exists
    club = db.query(models.Club).filter(models.Club.name == club_name_clean).first()
    
    if not club:
        # Create new club using new model
        club = models.Club(
            name=club_name_clean,
            owner_id=user.id,
            description=f"Club créé par {user.username}"
        )
        db.add(club)
        db.commit()
        db.refresh(club)
    
    # Join club
    user.club_id = club.id
    # Deprecated field sync for safety
    user.club_affiliation = club.name 
    db.commit()
    
    return RedirectResponse(url="/club", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/leave")
async def leave_club(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    user.club_id = None
    user.club_affiliation = None
    db.commit()
    return RedirectResponse(url="/club", status_code=status.HTTP_303_SEE_OTHER)

# --- ADMIN ENDPOINTS ---

@router.get("/admin", response_class=HTMLResponse)
async def club_admin_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    
    if not user.club_id:
        return RedirectResponse(url="/club")
        
    club = db.query(models.Club).filter(models.Club.id == user.club_id).first()
    
    # Security check
    if club.owner_id != user.id:
        # Not authorized
        return RedirectResponse(url="/club")
        
    members = db.query(models.User).filter(models.User.club_id == club.id).all()

    return templates.TemplateResponse("club_admin.html", {
        "request": request,
        "user": user,
        "club": club,
        "members": members
    })

@router.post("/admin/update")
async def update_club_details(
    request: Request,
    description: str = Form(None),
    website_url: str = Form(None),
    instagram_url: str = Form(None),
    strava_club_url: str = Form(None),
    profile_picture: str = Form(None),
    cover_picture: str = Form(None),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    if not user.club_id:
        return RedirectResponse(url="/club")
        
    club = db.query(models.Club).filter(models.Club.id == user.club_id).first()
    
    if club.owner_id != user.id:
        return RedirectResponse(url="/club")
        
    # Update fields
    if description is not None: club.description = description
    if website_url is not None: club.website_url = website_url
    if instagram_url is not None: club.instagram_url = instagram_url
    if strava_club_url is not None: club.strava_club_url = strava_club_url
    if profile_picture is not None: club.profile_picture = profile_picture
    if cover_picture is not None: club.cover_picture = cover_picture
    
    db.commit()
    
    return RedirectResponse(url="/club/admin", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/admin/kick")
async def kick_member(
    request: Request,
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    current_user = await get_current_user(request, db)
    if not current_user.club_id:
        return RedirectResponse(url="/club")
        
    club = db.query(models.Club).filter(models.Club.id == current_user.club_id).first()
    
    if club.owner_id != current_user.id:
        return RedirectResponse(url="/club")
        
    # Prevent self-kick
    if user_id == current_user.id:
        return RedirectResponse(url="/club/admin?error=Impossible de s'exclure soi-même")
        
    member_to_kick = db.query(models.User).filter(models.User.id == user_id, models.User.club_id == club.id).first()
    
    if member_to_kick:
        member_to_kick.club_id = None
        member_to_kick.club_affiliation = None
        db.commit()
        
    return RedirectResponse(url="/club/admin", status_code=status.HTTP_303_SEE_OTHER)
