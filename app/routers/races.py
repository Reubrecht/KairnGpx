from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import get_db, get_current_user_optional, templates

router = APIRouter()

@router.get("/event/{event_id}", response_class=HTMLResponse)
async def event_detail(event_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    
    event = db.query(models.RaceEvent).filter(models.RaceEvent.id == event_id).first()
    if not event:
        # Fallback by slug?
        return RedirectResponse(url="/explore")

    # Fetch editions ordered by year desc
    editions = db.query(models.RaceEdition).filter(models.RaceEdition.event_id == event.id).order_by(models.RaceEdition.year.desc()).all()

    return templates.TemplateResponse("event.html", {
        "request": request,
        "event": event,
        "editions": editions,
        "user": user
    })

@router.get("/race/{race_slug}", response_class=HTMLResponse)
async def race_detail(request: Request, race_slug: str, db: Session = Depends(get_db)):
    # Fetch Event with Editions and Routes
    event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == race_slug).first()
    if not event:
        raise HTTPException(status_code=404, detail="Race Event not found")
        
    # Group routes by Name (e.g. "UTMB", "CCC") to show latest first
    grouped_routes = {}
    
    # Flatten all routes from all editions
    all_routes = []
    for edition in event.editions:
        for route in edition.routes:
            route.year = edition.year
            route.edition_status = edition.status
            all_routes.append(route)
            
    # Sort by Year Descending
    all_routes.sort(key=lambda r: r.year, reverse=True)
    
    for route in all_routes:
        key = route.name 
        if key not in grouped_routes:
            grouped_routes[key] = {
                "latest": route,
                "history": [],
                "distance_category": route.distance_category
            }
        else:
            grouped_routes[key]["history"].append(route)

    return templates.TemplateResponse("race_detail.html", {
        "request": request,
        "event": event,
        "grouped_routes": grouped_routes,
        "user": await get_current_user_optional(request, db)
    })
