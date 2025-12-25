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
    # We want a list of members with their aggregated stats for the period
    # Query StravaActivity
    
    leaderboard = []
    
    for member in members:
        query = db.query(
            func.sum(models.StravaActivity.distance).label("total_dist"),
            func.sum(models.StravaActivity.total_elevation_gain).label("total_elev"),
            func.sum(models.StravaActivity.moving_time).label("total_time")
        ).filter(models.StravaActivity.user_id == member.id)
        
        if start_date:
            query = query.filter(models.StravaActivity.start_date >= start_date)
            
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
    
    # Club Totals (Sum of topstats or all? Let's sum all members in period)
    total_km = sum(e["dist_km"] for e in leaderboard)
    total_elev = sum(e["elev_m"] for e in leaderboard)

    return templates.TemplateResponse("club.html", {
        "request": request,
        "user": user,
        "has_club": True,
        "club_name": club_name,
        "members": members,
        "member_count": len(members),
        "leaderboard": leaderboard,
        "current_period": period,
        "current_metric": metric,
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
