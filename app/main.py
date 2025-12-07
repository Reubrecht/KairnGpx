import hashlib
import os
import shutil
from typing import List, Optional
import re
import unicodedata

from fastapi import FastAPI, Depends, Request, UploadFile, File, Form, HTTPException, status, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import between, or_
from sqlalchemy.orm import Session
from geopy.geocoders import Nominatim
import gpxpy
import gpxpy.gpx

# Auth Dependencies
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

from . import models, database

# Create tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Kairn Trail Platform")

# SECURITY CONFIG
SECRET_KEY = "supersecretkeychangeinproduction" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 1 week

# Changed to pbkdf2_sha256 to avoid bcrypt version conflicts
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Mount static files
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth Helpers
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user_optional(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    
    user = db.query(models.User).filter(models.User.username == username).first()
    return user

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

# Helpers (Geocoding etc)
def calculate_file_hash(file_content: bytes) -> str:
    return hashlib.sha256(file_content).hexdigest()

def get_location_info(lat: float, lon: float):
    geolocator = Nominatim(user_agent="kairn_trail_app_v1")
    try:
        location = geolocator.reverse(f"{lat}, {lon}", language="fr", timeout=5)
        if location and location.raw.get('address'):
            address = location.raw['address']
            city = address.get('city') or address.get('town') or address.get('village') or address.get('hamlet') or "Unknown"
            region = address.get('state') or address.get('region') or address.get('county') or "Unknown"
            return city, region
    except Exception as e:
        print(f"Geocoding error: {e}")
    return "Unknown", "Unknown"

def slugify(text: str) -> str:
    # Normalized + remove accents
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    text = re.sub(r'[^\w\s-]', '', text).lower()
    return re.sub(r'[-\s]+', '-', text).strip('-')

# Routes

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Check if user exists
        if db.query(models.User).filter(or_(models.User.username == username, models.User.email == email)).first():
            return templates.TemplateResponse("register.html", {"request": request, "error": "Ce nom d'utilisateur ou email existe déjà."})
        
        hashed_pwd = get_password_hash(password)
        user = models.User(username=username, email=email, hashed_password=hashed_pwd)
        db.add(user)
        db.commit()
        
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        print(f"REGISTER ERROR: {e}")
        import traceback
        traceback.print_exc()
        return templates.TemplateResponse("register.html", {"request": request, "error": f"Erreur serveur: {str(e)}"})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
    
    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    technicity: Optional[str] = None,
    city_search: Optional[str] = None,
    is_high_mountain: Optional[bool] = None
):
    user = await get_current_user_optional(request, db)
    query = db.query(models.Track)
    
    if technicity and technicity != "ALL":
        query = query.filter(models.Track.technicity == technicity)
    
    if city_search:
        query = query.filter(models.Track.location_city.ilike(f"%{city_search}%"))

    if is_high_mountain:
        query = query.filter(models.Track.is_high_mountain == True)

    tracks = query.order_by(models.Track.created_at.desc()).all()
    
    # Enum values for filters
    technicity_options = [e.value for e in models.TechnicityEnum]

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "tracks": tracks,
        "technicity_options": technicity_options,
        "user": user
    })

@app.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db) # Force login
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "status_options": [e.value for e in models.StatusEnum],
        "technicity_options": [e.value for e in models.TechnicityEnum],
        "terrain_options": [e.value for e in models.TerrainEnum],
        "user": user
    })

from .services.analytics import GpxAnalytics

@app.post("/upload")
async def upload_track(
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    status_val: str = Form(...),
    technicity: str = Form(...),
    terrain: str = Form(...),
    is_high_mountain: bool = Form(False),
    is_coastal: bool = Form(False),
    is_forest: bool = Form(False),
    is_urban: bool = Form(False),
    is_desert: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Read & Hash
    content = await file.read()
    file_hash = calculate_file_hash(content)

    # 2. Check Duplicates
    existing_track = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
    if existing_track:
        raise HTTPException(status_code=409, detail="This GPX file has already been uploaded.")

    # 3. Analyze GPX
    analytics = GpxAnalytics(content)
    metrics = analytics.calculate_metrics()
    
    if not metrics:
         raise HTTPException(status_code=400, detail="Could not parse or analyze GPX file.")

    # 4. Geocoding
    start_lat, start_lon = metrics["start_coords"]
    city, region = get_location_info(start_lat, start_lon)
    
    # 5. Simplify and Save
    simplified_xml = analytics.simplify_track(epsilon=0.00005) # ~5m precision
    
    upload_dir = "app/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}.gpx")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(simplified_xml if simplified_xml else content.decode('utf-8'))

    # 6. Save to DB
    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    while db.query(models.Track).filter(models.Track.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    new_track = models.Track(
        title=title,
        slug=slug,
        description=description,
        user_id=current_user.username,
        
        # Metrics
        distance_km=metrics["distance_km"],
        elevation_gain=metrics["elevation_gain"],
        elevation_loss=metrics["elevation_loss"],
        max_altitude=metrics["max_altitude"],
        min_altitude=metrics["min_altitude"],
        avg_altitude=metrics["avg_altitude"],
        max_slope=metrics["max_slope"],
        avg_slope_uphill=metrics["avg_slope_uphill"],
        
        # Effort
        km_effort=metrics["km_effort"],
        itra_points_estim=metrics["itra_points_estim"],
        
        # Logistics
        route_type=metrics["route_type"],
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=metrics["end_coords"][0],
        end_lon=metrics["end_coords"][1],
        location_city=city,
        location_region=region,
        estimated_times=metrics["estimated_times"],

        # Categorization
        status=models.StatusEnum(status_val),
        technicity=models.TechnicityEnum(technicity),
        terrain=models.TerrainEnum(terrain),
        
        # Tags
        is_high_mountain=is_high_mountain,
        is_coastal=is_coastal,
        is_forest=is_forest,
        is_urban=is_urban,
        is_desert=is_desert,
        
        file_path=file_path,
        file_hash=file_hash
    )
    
    db.add(new_track)
    db.commit()
    db.refresh(new_track)

    return RedirectResponse(url=f"/track/{new_track.id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/track/{track_id}", response_class=HTMLResponse)
async def track_detail(track_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "track": track,
        "user": user
    })

@app.get("/raw_gpx/{track_id}")
def get_raw_gpx(track_id: int, db: Session = Depends(get_db)):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track or not os.path.exists(track.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    with open(track.file_path, "r", encoding="utf-8") as f:
        content = f.read()
    from fastapi.responses import Response
    return Response(content=content, media_type="application/gpx+xml")
