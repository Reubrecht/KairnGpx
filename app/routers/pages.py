from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..dependencies import get_db, templates, get_current_user_optional

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/explore")
    
    # Check Beta Cookie
    has_beta = request.cookies.get("beta_access_v2") == "granted"
    return templates.TemplateResponse("landing.html", {"request": request, "user": user, "has_beta": has_beta})

@router.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse("privacy_policy.html", {"request": request})
