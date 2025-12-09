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

def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')

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
            print("DEBUG AUTH: Username is None in payload")
            return None
    except JWTError as e:
        print(f"DEBUG AUTH: JWT Error: {e}")
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
    # Environments
    is_high_mountain: Optional[bool] = None,
    is_coastal: Optional[bool] = None,
    is_forest: Optional[bool] = None,
    is_urban: Optional[bool] = None,
    is_desert: Optional[bool] = None,
    # New Standard Filters
    status_val: Optional[str] = None,
    terrain: Optional[str] = None,
    # New Slider Filters
    min_dist: Optional[float] = None,
    max_dist: Optional[float] = None,
    min_elev: Optional[float] = None,
    max_elev: Optional[float] = None,
    author: Optional[str] = None,
    # New Radius Filter
    radius: Optional[int] = 50,
    search_lat: Optional[str] = None,
    search_lon: Optional[str] = None
):
    user = await get_current_user_optional(request, db)
    query = db.query(models.Track)
    
    # 1. Technicity
    if technicity and technicity != "ALL":
        query = query.filter(models.Track.technicity == technicity)
    
    # 2. Status (Activity Type)
    if status_val and status_val != "ALL":
        query = query.filter(models.Track.status == status_val)

    # 3. Terrain
    if terrain and terrain != "ALL":
        query = query.filter(models.Track.terrain == terrain)

    # 4. City Search (Geo Radius)
    if city_search:
        try:
            lat, lon = None, None
            
            # Priority 1: Direct Coordinates from Autocomplete
            # Handle empty strings from form
            if search_lat and search_lon:
                try:
                    lat = float(search_lat)
                    lon = float(search_lon)
                except ValueError:
                    lat, lon = None, None
            
            # Priority 2: Geocoding (Fallback)
            if lat is None or lon is None:
                from geopy.geocoders import Nominatim
                geolocator = Nominatim(user_agent="kairn_app")
                location = geolocator.geocode(city_search)
                if location:
                    lat, lon = location.latitude, location.longitude

            if lat is not None and lon is not None:
                import math
                # Bounding Box Filter (Approximate)
                # 1 degree lat ~= 111 km
                lat_delta = radius / 111.0
                # 1 degree lon ~= 111 km * cos(lat)
                lon_delta = radius / (111.0 * abs(math.cos(math.radians(lat)))) if abs(math.cos(math.radians(lat))) > 0.01 else 0

                query = query.filter(
                    models.Track.start_lat.between(lat - lat_delta, lat + lat_delta),
                    models.Track.start_lon.between(lon - lon_delta, lon + lon_delta)
                )
            else:
                 query = query.filter(models.Track.location_city.ilike(f"%{city_search}%"))
        except Exception as e:
            print(f"Geocoding error: {e}")
            query = query.filter(models.Track.location_city.ilike(f"%{city_search}%"))

    # 5. Environments
    if is_high_mountain:
        query = query.filter(models.Track.is_high_mountain == True)
    if is_coastal:
        query = query.filter(models.Track.is_coastal == True)
    if is_forest:
        query = query.filter(models.Track.is_forest == True)
    if is_urban:
        query = query.filter(models.Track.is_urban == True)
    if is_desert:
        query = query.filter(models.Track.is_desert == True)

    # 6. Distance
    if min_dist is not None:
        query = query.filter(models.Track.distance_km >= min_dist)
    if max_dist is not None:
        query = query.filter(models.Track.distance_km <= max_dist)

    # 7. Elevation
    if min_elev is not None:
        query = query.filter(models.Track.elevation_gain >= min_elev)
    if max_elev is not None:
        query = query.filter(models.Track.elevation_gain <= max_elev)

    # 8. Author
    if author:
        query = query.filter(models.Track.user_id.ilike(f"%{author}%"))

    tracks = query.order_by(models.Track.created_at.desc()).all()
    
    # Enum values for filters
    technicity_options = [e.value for e in models.TechnicityEnum]
    status_options = [e.value for e in models.StatusEnum]
    terrain_options = [e.value for e in models.TerrainEnum]

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "tracks": tracks,
        "technicity_options": technicity_options,
        "status_options": status_options,
        "terrain_options": terrain_options,
        "user": user,
        "current_radius": radius,
        "current_city": city_search
    })


@app.get("/search", response_class=HTMLResponse)
async def advanced_search(
    request: Request,
    db: Session = Depends(get_db),
    location: Optional[str] = None,
    min_dist: Optional[float] = None,
    max_dist: Optional[float] = None,
    min_elev: Optional[float] = None,
    max_elev: Optional[float] = None,
    technicity: Optional[str] = None,
    author: Optional[str] = None,
):
    user = await get_current_user_optional(request, db)
    query = db.query(models.Track)

    # 1. Location (City) - Could expand to country if we stored it separately or parsed it
    if location:
        # Simple ILIKE search on city field for now. 
        # Future: use pycountry to detect if 'location' is a country and search a 'country' code column if it existed.
        query = query.filter(models.Track.location_city.ilike(f"%{location}%"))

    # 2. Distance
    if min_dist is not None:
        query = query.filter(models.Track.distance_km >= min_dist)
    if max_dist is not None:
        query = query.filter(models.Track.distance_km <= max_dist)

    # 3. Elevation
    if min_elev is not None:
        query = query.filter(models.Track.elevation_gain >= min_elev)
    if max_elev is not None:
        query = query.filter(models.Track.elevation_gain <= max_elev)

    # 4. Technicity
    if technicity and technicity != "":
        query = query.filter(models.Track.technicity == technicity)

    # 5. Author
    if author:
        query = query.filter(models.Track.user_id.ilike(f"%{author}%"))

    # Visibility: Public unless it's my own track
    # Logic: Show PUBLIC OR (PRIVATE AND owner==me)
    # For simplicity in search, we might only show PUBLIC results unless we add complex OR logic.
    # Let's stick to Public + My Tracks logic if user is logged in, or just Public.
    if user:
         query = query.filter(or_(models.Track.visibility == models.Visibility.PUBLIC, models.Track.user_id == user.username))
    else:
         query = query.filter(models.Track.visibility == models.Visibility.PUBLIC)

    tracks = query.order_by(models.Track.created_at.desc()).all()

    return templates.TemplateResponse("search.html", {
        "request": request,
        "tracks": tracks,
        "user": user,
        "technicity_options": [e.value for e in models.TechnicityEnum],
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
    # Environment List (Multi-select)
    environment: List[str] = Form([]),
    # New Fields
    visibility: str = Form("public"),
    tags: str = Form(None), # Comma separated
    water_points_count: int = Form(0),
    scenery_rating: int = Form(None),
    
    # Official Race Fields
    race_name: Optional[str] = Form(None),
    race_year: Optional[int] = Form(None),
    race_category: Optional[str] = Form(None),
    
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
        # User-friendly error
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "error": f"Cette trace existe déjà : '{existing_track.title}' (importée le {existing_track.created_at.strftime('%d/%m/%Y')})",
            "user": current_user,
            "status_options": [e.value for e in models.StatusEnum],
            "technicity_options": [e.value for e in models.TechnicityEnum],
            "terrain_options": [e.value for e in models.TerrainEnum]
        })

    # 3. Analyze GPX
    analytics = GpxAnalytics(content)
    metrics = analytics.calculate_metrics()
    inferred = analytics.infer_attributes(metrics)
    
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

    # 6. Race Logic
    race_id = None
    if status_val == "OFFICIAL_RACE" and race_name:
        race_slug = slugify(race_name)
        existing_race = db.query(models.OfficialRace).filter(models.OfficialRace.slug == race_slug).first()
        if not existing_race:
            existing_race = models.OfficialRace(
                name=race_name,
                slug=race_slug,
                description=f"Événement créé lors de l'import de la trace {title}."
            )
            db.add(existing_race)
            db.commit()
            db.refresh(existing_race)
        race_id = existing_race.id

    # 7. Save to DB
    base_slug = slugify(title)
    slug = base_slug
    counter = 1
    while db.query(models.Track).filter(models.Track.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    new_track = models.Track(
        title=title,
        slug=slug,
        race_id=race_id,
        race_year=race_year,
        race_category=race_category,
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
        
        # Tags & Extras
        # Map core booleans from environment list
        is_high_mountain=("high_mountain" in environment) or inferred["is_high_mountain"],
        is_coastal="coastal" in environment,
        is_forest="forest" in environment,
        is_urban="urban" in environment,
        is_desert="desert" in environment,
        
        # Merge User Tags + Extra Environments + Inferred Tags
        tags=list(set(
            ([t.strip() for t in tags.split(',')] if tags else []) +
            [e for e in environment if e not in ["high_mountain", "coastal", "forest", "urban", "desert"]] +
            inferred["tags"]
        )),
        
        file_path=file_path,
        file_hash=file_hash,

        # New Fields
        visibility=models.Visibility(visibility),
        water_points_count=water_points_count,
        scenery_rating=scenery_rating
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

@app.get("/race/{slug}", response_class=HTMLResponse)
async def race_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    race = db.query(models.OfficialRace).filter(models.OfficialRace.slug == slug).first()
    if not race:
        raise HTTPException(status_code=404, detail="Course non trouvée")
    
    # Tracks linked to this race (ordered by year descending, then distance)
    tracks = db.query(models.Track).filter(models.Track.race_id == race.id).order_by(models.Track.race_year.desc()).all()
    
    return templates.TemplateResponse("race_detail.html", {
        "request": request, 
        "race": race, 
        "tracks": tracks,
        "user": user
    })

@app.get("/raw_gpx/{track_id}")
def get_raw_gpx(track_id: int, db: Session = Depends(get_db)):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Reconstruct path safely for Docker environment
    # We use the file_hash to find the file in the uploads directory
    safe_path = os.path.join("app/uploads", f"{track.file_hash}.gpx")
    
    if not os.path.exists(safe_path):
        # Fallback: check if the stored path exists (legacy)
        if os.path.exists(track.file_path):
             safe_path = track.file_path
        else:
             print(f"File missing: {safe_path} (Hash: {track.file_hash})")
             raise HTTPException(status_code=404, detail="GPX File not found on server")
    
    with open(safe_path, "r", encoding="utf-8") as f:
        content = f.read()
    from fastapi.responses import Response
    return Response(content=content, media_type="application/gpx+xml")

# --- EDIT TRACKS ---
@app.get("/track/{track_id}/edit", response_class=HTMLResponse)
async def edit_track_form(track_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
        
    # Permission check
    if track.user_id != user.username and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    return templates.TemplateResponse("edit_track.html", {
        "request": request,
        "track": track,
        "user": user,
        "status_options": [e.value for e in models.StatusEnum],
        "technicity_options": [e.value for e in models.TechnicityEnum],
        "terrain_options": [e.value for e in models.TerrainEnum]
    })

@app.post("/track/{track_id}/edit")
async def edit_track_action(
    track_id: int, 
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    visibility: str = Form(...),
    status_val: str = Form(...),
    technicity: str = Form(...),
    terrain: str = Form(...),
    scenery_rating: int = Form(None),
    water_points_count: int = Form(0),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
        
    if track.user_id != user.username and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update Fields
    track.title = title
    track.description = description
    track.visibility = models.Visibility(visibility)
    track.status = models.StatusEnum(status_val)
    track.technicity = models.TechnicityEnum(technicity)
    track.terrain = models.TerrainEnum(terrain)
    track.scenery_rating = scenery_rating
    track.water_points_count = water_points_count
    
    db.commit()
    
    return RedirectResponse(url=f"/track/{track_id}", status_code=303)



# --- MAP & VISUALIZATIONS ---

@app.get("/map", response_class=HTMLResponse)
async def global_map_page(request: Request, db: Session = Depends(get_db)):
    # Optional: require login
    user = await get_current_user_optional(request, db)
    
    # Fetch content (optimally select only needed fields: lat/lon/id)
    tracks = db.query(models.Track).filter(models.Track.visibility == models.Visibility.PUBLIC).all()
    
    # We pass 'total_tracks' for the counter in UI
    return templates.TemplateResponse("heatmap.html", {
        "request": request,
        "tracks": tracks,
        "total_tracks": len(tracks),
        "user": user
    })

# --- PROFILES & ADMIN ---

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    # Fetch user's tracks
    tracks = db.query(models.Track).filter(models.Track.user_id == user.username).order_by(models.Track.created_at.desc()).all()
    
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "tracks": tracks
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if not user.is_admin:
        return RedirectResponse(url="/", status_code=303)
        
    all_users = db.query(models.User).all()
    all_tracks = db.query(models.Track).order_by(models.Track.created_at.desc()).all()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "users": all_users,
        "tracks": all_tracks
    })

@app.post("/track/{track_id}/delete")
async def delete_track_action(track_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
        
    # Permission check: Owner or Admin
    if track.user_id != user.username and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        # Delete file if possible (optional, but good for cleanup)
        # Reconstruct path logic similar to get_raw_gpx
        safe_path = os.path.join("app/uploads", f"{track.file_hash}.gpx")
        if os.path.exists(safe_path):
            os.remove(safe_path)
    except Exception as e:
        print(f"Error deleting file: {e}")

    db.delete(track)
    db.commit()
    
    # Redirect based on where they came from (Referer) or default to profile
    referer = request.headers.get("referer", "/profile")
    return RedirectResponse(url=referer, status_code=303)

@app.post("/admin/delete_user/{user_id}")
async def delete_user_action(user_id: int, request: Request, db: Session = Depends(get_db)):
    current_admin = await get_current_user(request, db)
    if not current_admin.is_admin:
         raise HTTPException(status_code=403, detail="Admin only")
         
    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()
    if user_to_delete:
        # Delete user's tracks first (or rely on DB cascading if set, but explicit is safer here)
        db.query(models.Track).filter(models.Track.user_id == user_to_delete.username).delete()
        db.delete(user_to_delete)
        db.commit()
        
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/make_me_admin")
async def make_me_admin(request: Request, db: Session = Depends(get_db)):
    """Secret endpoint to become admin for testing purposes"""
    user = await get_current_user(request, db)
    user.is_admin = True
    db.commit()
    return RedirectResponse(url="/profile", status_code=303)
