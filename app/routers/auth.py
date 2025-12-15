import os
import shutil
import traceback
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, status, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .. import models
from ..dependencies import (
    get_db, 
    templates, 
    verify_password, 
    get_password_hash, 
    create_access_token
)

router = APIRouter()

@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@router.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(None),
    invitation_code: str = Form(None),
    
    # New Fields
    profile_picture: Optional[UploadFile] = File(None),
    location_city: Optional[str] = Form(None),
    location_region: Optional[str] = Form(None),
    location_country: Optional[str] = Form(None),
    location_lat: Optional[float] = Form(None),
    location_lon: Optional[float] = Form(None),
    
    db: Session = Depends(get_db)
):
    try:
        # 1. Check Invitation Code (Beta Lock)
        required_code = os.getenv("INVITATION_CODE")
        if required_code:
            if not invitation_code or invitation_code.strip() != required_code:
                 return templates.TemplateResponse("register.html", {
                     "request": request, 
                     "error": "Code d'invitation incorrect. L'inscription est restreinte."
                 })

        # Check if user exists
        if db.query(models.User).filter(or_(models.User.username == username, models.User.email == email)).first():
            return templates.TemplateResponse("register.html", {"request": request, "error": "Ce nom d'utilisateur ou email existe déjà."})
        
        hashed_pwd = get_password_hash(password)
        
        # Construct User with new fields
        user = models.User(
            username=username, 
            email=email, 
            hashed_password=hashed_pwd,
            full_name=full_name,
            # Location Data
            location=location_city, # Fallback display
            location_city=location_city,
            location_region=location_region,
            location_country=location_country,
            location_lat=location_lat,
            location_lon=location_lon
        )
        
        db.add(user)
        db.commit() # Commit to get ID
        
        # Handle Profile Picture Upload
        if profile_picture and profile_picture.filename:
            try:
                upload_dir = Path("app/media/profiles")
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                ext = profile_picture.filename.split('.')[-1].lower()
                if ext in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                    filename = f"{user.id}.{ext}"
                    file_path = upload_dir / filename
                    
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(profile_picture.file, buffer)
                    
                    user.profile_picture = f"/media/profiles/{filename}"
                    db.commit()
            except Exception as e:
                print(f"Profile Pic Error: {e}")
        
        return RedirectResponse(url="/login?registered=True", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        traceback.print_exc()
        return templates.TemplateResponse("register.html", {"request": request, "error": f"Erreur serveur: {str(e)}"})

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
        
        access_token = create_access_token(data={"sub": user.username})
        response = RedirectResponse(url="/explore", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="access_token", 
            value=f"Bearer {access_token}", 
            httponly=True,
            max_age=60 * 60 * 24 * 30, # 30 days
            expires=60 * 60 * 24 * 30  # IE/Edge support
        )
        return response
    except Exception as e:
        with open("kairn_error.log", "a") as f:
            f.write(f"LOGIN ERROR: {str(e)}\n")
            f.write(traceback.format_exc())
            f.write("\n----------------\n")
        raise e

@router.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@router.post("/verify-beta")
async def verify_beta(request: Request, code: str = Form(...)):
    required_code = os.getenv("INVITATION_CODE", "ARC2025") # Default fallback if env not set
    if code and code.strip() == required_code:
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="beta_access_v2", value="granted", max_age=60*60*24*30, httponly=True) # 30 days
        return response
    else:
        return templates.TemplateResponse("landing.html", {
            "request": request, 
            "error": "Code incorrect.",
            "has_beta": False
        })
