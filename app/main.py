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
from dotenv import load_dotenv

# Load local env only if file exists (Local Dev)
if os.path.exists("local.env"):
    load_dotenv("local.env", override=True)

import gpxpy
import gpxpy
import gpxpy.gpx
import markdown

# Auth Dependencies
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

from . import models, database
import json
from .version import __version__ as app_version # Import version

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

app = FastAPI(title="Kairn Trail Platform", version=app_version)

# SECURITY CONFIG
SECRET_KEY = "supersecretkeychangeinproduction" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # 1 hour

# Changed to pbkdf2_sha256 to avoid bcrypt version conflicts
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Mount static files
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")
templates.env.globals['version'] = app_version # Inject version globally

# Custom Filters
def markdown_filter(text):
    if text:
        return markdown.markdown(text)
    return ""

templates.env.filters['markdown'] = markdown_filter

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

async def get_current_active_user(current_user: models.User = Depends(get_current_user)):
    return current_user

async def get_current_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role not in [models.Role.ADMIN, models.Role.SUPER_ADMIN] and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return current_user

async def get_current_super_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != models.Role.SUPER_ADMIN:
         raise HTTPException(status_code=403, detail="Super Admin privileges required")
    return current_user

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
    full_name: str = Form(None), # Validate new field
    invitation_code: str = Form(None),
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
        # Add full_name to user creation
        user = models.User(
            username=username, 
            email=email, 
            hashed_password=hashed_pwd,
            full_name=full_name
        )
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
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})
        
        access_token = create_access_token(data={"sub": user.username})
        response = RedirectResponse(url="/explore", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
        return response
    except Exception as e:
        import traceback
        with open("kairn_error.log", "a") as f:
            f.write(f"LOGIN ERROR: {str(e)}\n")
            f.write(traceback.format_exc())
            f.write("\n----------------\n")
        raise e

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.get("/", response_class=HTMLResponse)

async def landing_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    if user:
        return RedirectResponse(url="/explore")
    
    # Check Beta Cookie
    has_beta = request.cookies.get("beta_access_v2") == "granted"
    return templates.TemplateResponse("landing.html", {"request": request, "user": user, "has_beta": has_beta})

@app.post("/verify-beta")
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

@app.get("/explore", response_class=HTMLResponse)
async def explore(
    request: Request,
    db: Session = Depends(get_db),
    city_search: Optional[str] = None,
    # New Standard Filters
    activity_type: Optional[str] = None,
    ratio_category: Optional[str] = None,
    is_official: Optional[bool] = None,
    # Sliders
    min_dist: Optional[float] = None,
    max_dist: Optional[float] = None,
    min_elev: Optional[float] = None,
    max_elev: Optional[float] = None,
    author: Optional[str] = None,
    # Radius & Geo
    radius: Optional[int] = 50,
    search_lat: Optional[str] = None,
    search_lon: Optional[str] = None,
    tag: Optional[str] = None
):
    try:
        user = await get_current_user_optional(request, db)
        has_beta = request.cookies.get("beta_access_v2") == "granted"
        if not user and not has_beta:
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
        query = db.query(models.Track)
        
        # 1. Activity Type
        if activity_type:
            query = query.filter(models.Track.activity_type == activity_type)

        # 2. Official Race
        if is_official:
            query = query.filter(models.Track.is_official_route == True)

        # 3. City/Radius Search
        current_city = city_search
        if city_search:
            try:
                lat, lon = None, None
                
                # Priority 1: Direct Coordinates from Autocomplete
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
                     # Fallback to simple string match
                     query = query.filter(models.Track.location_city.ilike(f"%{city_search}%"))
            except Exception as e:
                print(f"Geocoding error: {e}")
                query = query.filter(models.Track.location_city.ilike(f"%{city_search}%"))

        # 4. Distance
        if min_dist is not None:
            query = query.filter(models.Track.distance_km >= min_dist)
        if max_dist is not None:
            query = query.filter(models.Track.distance_km <= max_dist)

        # 5. Elevation
        if min_elev is not None:
            query = query.filter(models.Track.elevation_gain >= min_elev)
        if max_elev is not None:
            query = query.filter(models.Track.elevation_gain <= max_elev)

        # 6. Author
        if author:
            query = query.filter(models.Track.user_id.ilike(f"%{author}%"))
        
        # 7. Tags (JSON array contains)
        if tag:
            # SQLite JSON search (simplified for basic tags)
            query = query.filter(models.Track.tags.ilike(f'%"{tag}"%'))
            
        # Visibility
        if user:
             query = query.filter(or_(models.Track.visibility == models.Visibility.PUBLIC, models.Track.user_id == user.username))
        else:
             query = query.filter(models.Track.visibility == models.Visibility.PUBLIC)

        tracks = query.order_by(models.Track.created_at.desc()).all()
        
        
        # 8. Post-Processing for Ratio D+
        if ratio_category:
            filtered_tracks = []
            for t in tracks:
                if not t.distance_km or t.distance_km == 0:
                    continue
                ratio = t.elevation_gain / t.distance_km
                if ratio_category == "FLAT" and ratio < 15:
                    filtered_tracks.append(t)
                elif ratio_category == "ROLLING" and 15 <= ratio < 40:
                    filtered_tracks.append(t)
                elif ratio_category == "HILLY" and 40 <= ratio < 80:
                    filtered_tracks.append(t)
                elif ratio_category == "MOUNTAIN" and ratio >= 80:
                    filtered_tracks.append(t)
            tracks = filtered_tracks

        # 9. FETCH PENDING OFFICIAL RACES (Official Races without Track)
        # Grouped by Event
        if not author: 
            import re
            
            # Query routes without official track
            pending_query = db.query(models.RaceRoute).filter(models.RaceRoute.official_track_id == None)\
                .join(models.RaceEdition).join(models.RaceEvent)

            # Apply Location Filter (Region/Ville match)
            if city_search:
                 pending_query = pending_query.filter(models.RaceEvent.region.ilike(f"%{city_search}%"))
            
            pending_routes = pending_query.all()
            
            # Group by Event (via Edition)
            # key: event_id, value: MockEventObject
            grouped_events = {}

            for pr in pending_routes:
                event = pr.edition.event
                edition = pr.edition
                
                # Create wrapper if not exists
                if event.id not in grouped_events:
                    grouped_events[event.id] = {
                        "id": f"event_{event.id}",
                        "title": f"{event.name} {edition.year}", # Assume one active edition for now? Or group by edition too? 
                                                                  # Usually filtering by upcoming vs past. For now simplest is Event Name.
                        "location_city": event.region,
                        "created_at": datetime.now(), # To float to top
                        "is_grouped_event": True, # Flag for template
                        "routes": [],
                        "tags": ["Course Officielle", "Trace à venir"],
                        # Dummy fields for track compatibility
                        "distance_km": 0,
                        "elevation_gain": 0,
                        "user_id": "Official",
                        "map_thumbnail_url": None 
                    }
                
                # Parse Stats
                p_dist = 0
                p_elev = 0
                m_dist = re.search(r'(\d+)\s*km', pr.name, re.IGNORECASE)
                if m_dist: p_dist = int(m_dist.group(1))
                m_elev = re.search(r'(\d+)\s*m', pr.name, re.IGNORECASE)
                if m_elev: p_elev = int(m_elev.group(1))

                # Apply Filters to this route? 
                # If we filter routes, and an event has 0 matching routes, do we show the event?
                # Probably not.
                
                match_filters = True
                if min_dist is not None and p_dist < min_dist: match_filters = False
                if max_dist is not None and p_dist > max_dist: match_filters = False
                if min_elev is not None and p_elev < min_elev: match_filters = False
                if max_elev is not None and p_elev > max_elev: match_filters = False

                if match_filters:
                     grouped_events[event.id]["routes"].append({
                         "id": pr.id,
                         "name": pr.name,
                         "distance_km": p_dist,
                         "elevation_gain": p_elev
                     })
            
            # Add only events with at least one matching route
            class MockObj:
                 def __init__(self, **kwargs):
                        self.__dict__.update(kwargs)

            for ev_data in grouped_events.values():
                if len(ev_data["routes"]) > 0:
                    # Sort routes by distance
                    ev_data["routes"].sort(key=lambda x: x["distance_km"])
                    tracks.append(MockObj(**ev_data))

        
        # Collect unique tags
        all_visible_tracks = db.query(models.Track.tags).filter(models.Track.visibility == models.Visibility.PUBLIC).all()
        unique_tags = set()
        for t_row in all_visible_tracks:
            if t_row.tags:
                try:
                    tag_list = t_row.tags if isinstance(t_row.tags, list) else json.loads(t_row.tags)
                    for t in tag_list:
                        unique_tags.add(t)
                except:
                    pass
        sorted_tags = sorted(list(unique_tags))
        
        
        # Count actual tracks (excluding grouped events)
        real_track_count = len([t for t in tracks if not getattr(t, 'is_grouped_event', False)])

        return templates.TemplateResponse("index.html", {
            "request": request,
            "tracks": tracks,
            "real_track_count": real_track_count,
            "user": user,
            "active_page": "explore",
            "current_city": current_city,
            "radius": radius,
            "all_tags": sorted_tags,
            "current_tag": tag
        })
    except Exception as e:
        import traceback
        import sys
        error_msg = f"\n{'='*80}\nEXPLORE ENDPOINT ERROR\n{'='*80}\n{str(e)}\n{traceback.format_exc()}\n{'='*80}\n"
        print(error_msg, file=sys.stderr, flush=True)
        
        # Write to log file in app directory
        try:
            log_path = os.path.join(os.path.dirname(__file__), "..", "kairn_error.log")
            with open(log_path, "a") as f:
                f.write(error_msg)
        except Exception as log_err:
            print(f"Failed to write log: {log_err}", file=sys.stderr)
        
        raise e

@app.get("/search", response_class=HTMLResponse)
async def advanced_search(
    request: Request,
    db: Session = Depends(get_db),
    location: Optional[str] = None,
    min_dist: Optional[float] = None,
    max_dist: Optional[float] = None,
    min_elev: Optional[float] = None,
    max_elev: Optional[float] = None,
    activity_type: Optional[str] = None,
    ratio_category: Optional[str] = None,
    is_official: Optional[bool] = None,
    author: Optional[str] = None,
):
    user = await get_current_user_optional(request, db)
    has_beta = request.cookies.get("beta_access_v2") == "granted"
    if not user and not has_beta:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    query = db.query(models.Track)

    # 1. Location (City search based on contains)
    if location:
        # Simple wildcard search on city or region
        query = query.filter(or_(
            models.Track.location_city.ilike(f"%{location}%"),
            models.Track.location_region.ilike(f"%{location}%"),
            models.Track.title.ilike(f"%{location}%") # Also search title
        ))

    # 2. Activity Type
    if activity_type:
        query = query.filter(models.Track.activity_type == activity_type)

    # 3. Official Race
    if is_official:
        query = query.filter(models.Track.is_official_route == True)

    # 4. Distance
    if min_dist is not None:
        query = query.filter(models.Track.distance_km >= min_dist)
    if max_dist is not None:
        query = query.filter(models.Track.distance_km <= max_dist)

    # 5. Elevation
    if min_elev is not None:
        query = query.filter(models.Track.elevation_gain >= min_elev)
    if max_elev is not None:
        query = query.filter(models.Track.elevation_gain <= max_elev)

    # 6. Author
    if author:
        query = query.filter(models.Track.user_id.ilike(f"%{author}%"))

    # Visibility
    if user:
         query = query.filter(or_(models.Track.visibility == models.Visibility.PUBLIC, models.Track.user_id == user.username))
    else:
         query = query.filter(models.Track.visibility == models.Visibility.PUBLIC)

    # Execute main query to list tracks
    tracks = query.order_by(models.Track.created_at.desc()).all()

    # 7. Post-Processing for Ratio D+ (Sqlite division is tricky/unsafe sometimes, Python is easier for small scale)
    if ratio_category:
        filtered_tracks = []
        for t in tracks:
            if not t.distance_km or t.distance_km == 0:
                continue
            
            ratio = t.elevation_gain / t.distance_km # m/km
            
            if ratio_category == "FLAT" and ratio < 15:
                filtered_tracks.append(t)
            elif ratio_category == "ROLLING" and 15 <= ratio < 40:
                filtered_tracks.append(t)
            elif ratio_category == "HILLY" and 40 <= ratio < 80:
                filtered_tracks.append(t)
            elif ratio_category == "MOUNTAIN" and ratio >= 80:
                filtered_tracks.append(t)
        
        tracks = filtered_tracks

    return templates.TemplateResponse("search.html", {
        "request": request,
        "tracks": tracks,
        "user": user,
    })

@app.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request, db: Session = Depends(get_db), race_route_id: Optional[int] = None):
    user = await get_current_user(request, db) # Force login
    
    prefill_race = None
    if race_route_id:
        # Fetch race details to prefill form
        route = db.query(models.RaceRoute).filter(models.RaceRoute.id == race_route_id).first()
        if route:
            prefill_race = {
                "id": route.id,
                "name": route.edition.event.name,
                "year": route.edition.year,
                "route_name": route.name,
                "category": route.distance_category
            }

    # Fetch all race events for dropdown
    race_events = db.query(models.RaceEvent).order_by(models.RaceEvent.name).all()

    return templates.TemplateResponse("upload.html", {
        "request": request,
        "status_options": [], # [e.value for e in models.StatusEnum],
        "technicity_options": [], # [e.value for e in models.TechnicityEnum],
        "terrain_options": [], # [e.value for e in models.TerrainEnum],
        "user": user,
        "prefill_race": prefill_race,
        "race_events": race_events
    })

from .services.analytics import GpxAnalytics
from .services.ai_analyzer import AiAnalyzer

@app.post("/upload")
async def upload_track(
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    # Removed technicity/terrain forms
    # Environment List (Multi-select)
    environment: List[str] = Form([]),
    # New Fields
    visibility: str = Form("public"),
    activity_type: str = Form("TRAIL_RUNNING"),
    tags: str = Form(None), # Comma separated
    water_points_count: int = Form(0),
    scenery_rating: int = Form(None),
    
    # Official Race Fields
    is_official_bot: bool = Form(False),
    linked_race_route_id: Optional[int] = Form(None), # FROM HIDDEN INPUT
    race_name: Optional[str] = Form(None),
    race_year: Optional[int] = Form(None),
    race_route_name: Optional[str] = Form(None),
    
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
            "status_options": [], # Removed
            "technicity_options": [], # Removed
            "terrain_options": [] # Removed
        })

    # 3. Analyze GPX
    analytics = GpxAnalytics(content)
    metrics = analytics.calculate_metrics()
    inferred = analytics.infer_attributes(metrics)
    gpx_meta = analytics.get_metadata() # Extract internal GPX metadata
    
    # 4. Apply GPX Metadata (Fallback/Default)
    # If the user provided title looks like a filename (contains .gpx) and we have a better internal name, use it.
    # Or simply if we have an internal name, append or prefer it? 
    # Let's say: if current 'title' is just the filename (heuristic), and gpx_meta['name'] exists, use gpx_meta['name'].
    # The form usually sends filename if user didn't type.
    if gpx_meta.get("name") and (title.lower().endswith(".gpx") or title == "Trace"):
        title = gpx_meta["name"]
        
    if not description and gpx_meta.get("description"):
        description = gpx_meta["description"]
        
    if gpx_meta.get("keywords"):
        # keywords is usually a comma-sep string or list? gpxpy returns string or list depending on version? 
        # usually string "tag1, tag2"
        kws = gpx_meta["keywords"]
        if isinstance(kws, str):
            inferred["tags"].extend([k.strip() for k in kws.split(",") if k.strip()])
        elif isinstance(kws, list):
             inferred["tags"].extend(kws)
    
    if not metrics:
         raise HTTPException(status_code=400, detail="Could not parse or analyze GPX file.")

    # 3b. AI Enrichment (Gemini)
    try:
        ai_analyzer = AiAnalyzer()
        # Only call if API key is present to save time/errors, handled in class but good to be explicit
        if ai_analyzer.model:
            print("Calling Gemini for analysis...")
            ai_data = ai_analyzer.analyze_track(metrics, metadata=gpx_meta, user_title=title, is_race=is_official_bot)
            
            # Auto-fill description if empty OR if we only have generic GPX desc?
            # AI description is usually better structured.
            if ai_data.get("ai_description"):
                if description:
                     description += "\n\n" + ai_data["ai_description"] # Append if existing
                else:
                     description = ai_data["ai_description"]
            
            # Use AI Title if generated (Override if title seems generic)
            if ai_data.get("ai_title"):
                # If we still have a filename-like title, overwrite. 
                # Otherwise, maybe AI title is better? Let's overwrite for consistency.
                title = ai_data["ai_title"]
                
            # Append AI tags
            if ai_data.get("ai_tags"):
                inferred["tags"].extend(ai_data["ai_tags"])
                
    except Exception as e:
        print(f"AI Integration skipped: {e}")

    # 4. Geocoding (Renumbered logic flow, but code remains same)
    start_lat, start_lon = metrics["start_coords"]
    city, region = get_location_info(start_lat, start_lon)
    
    # 5. Simplify and Save
    simplified_xml = analytics.simplify_track(epsilon=0.00005) # ~5m precision
    
    upload_dir = "app/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}.gpx")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(simplified_xml if simplified_xml else content.decode('utf-8'))

    # 6. Race Logic (Event & Edition creation)
    race_route_obj = None
    is_official = False
    
    if is_official_bot and race_name and race_year:
        try:
            is_official = True
            # 1. Event
            event_slug = slugify(race_name)
            event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == event_slug).first()
            if not event:
                event = models.RaceEvent(name=race_name, slug=event_slug)
                db.add(event)
                db.commit()
                db.refresh(event)
            
            # 2. Edition
            edition = db.query(models.RaceEdition).filter(models.RaceEdition.event_id == event.id, models.RaceEdition.year == race_year).first()
            if not edition:
                edition = models.RaceEdition(event_id=event.id, year=race_year)
                db.add(edition)
                db.commit()
                db.refresh(edition)
                
            # 3. Route (will be linked after track creation)
             # We prepare data but creation happens after track has ID? 
             # Actually we can create it after.
        except Exception as e:
            print(f"Race logic error: {e}")

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
        description=description,
        user_id=current_user.username,
        
        # New Enums & Booleans
        activity_type=models.ActivityType(activity_type),
        is_official_route=is_official,
        
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
        ibp_index=metrics.get("ibp_index"),
        longest_climb=metrics.get("longest_climb"),
        
        # Logistics
        route_type=metrics["route_type"],
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=metrics["end_coords"][0],
        end_lon=metrics["end_coords"][1],
        location_city=city,
        location_region=region,
        estimated_times=metrics["estimated_times"],

        # Categorization - Removed deprecated fields
        # status=models.StatusEnum(status_val),
        # technicity=models.TechnicityEnum(technicity),
        # terrain=models.TerrainEnum(terrain),
        
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
    
    # 8. Finalize Race Linking if needed
    if is_official and 'edition' in locals():
        try:
            new_race_route = models.RaceRoute(
                edition_id=edition.id,
                name=race_route_name or title, # Default to track title if route name not given
                official_track_id=new_track.id
            )
            db.add(new_race_route)
            db.commit()
        except Exception as e:
            print(f"Failed to create RaceRoute: {e}")


    # 9. Link to Official Race (Pre-existing)
    if linked_race_route_id:
        race_route = db.query(models.RaceRoute).filter(models.RaceRoute.id == linked_race_route_id).first()
        if race_route:
            print(f"Linking Track {new_track.id} to Official Route {race_route.name}")
            race_route.official_track_id = new_track.id
            
            # Enforce Official Status
            new_track.is_official_route = True
            new_track.status = models.StatusEnum.RACE
            new_track.user_id = "Official" # Or keep uploader? Usually Official tracks are owned by admin/system, but Moderator upload is fine.
                                          # Let's keep the uploader so we know who did it, but mark as is_official_route=True.
            
            # Auto-fill metadata from Race if missing?
            # Already handled by form inputs usually.
            
            db.commit()

    return RedirectResponse(url=f"/track/{new_track.id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/event/{event_id}", response_class=HTMLResponse)
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

@app.get("/track/{track_identifier}", response_class=HTMLResponse)
async def track_detail(track_identifier: str, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    has_beta = request.cookies.get("beta_access_v2") == "granted"
    if not user and not has_beta:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    # Try ID first, then Slug
    track = None
    if track_identifier.isdigit():
        track = db.query(models.Track).filter(models.Track.id == int(track_identifier)).first()
    
    if not track:
        # Try as slug
        track = db.query(models.Track).filter(models.Track.slug == track_identifier).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    
    # Generate GeoJSON for MapLibre
    import os
    track_geojson = None
    if os.path.exists(track.file_path):
        with open(track.file_path, "r", encoding="utf-8") as f:
            content = f.read()
            analytics = GpxAnalytics(content)
            track_geojson = analytics.get_geojson()
            
            # --- Lazy AI Analysis (Trigger if missing tags/desc) ---
            # Check if analysis is needed (e.g. no tags or very short desc)
            has_tags = track.tags and (isinstance(track.tags, list) and len(track.tags) > 0)
            needs_analysis = not has_tags or not track.description or len(track.description) < 20
            
            if needs_analysis:
                try:
                    # We need metrics and metadata for AI
                    metrics = analytics.calculate_metrics()
                    gpx_meta = analytics.get_metadata()
                    
                    ai_analyzer = AiAnalyzer()
                    if ai_analyzer.model:
                        print(f"Lazy Analysis triggered for Track {track.id}...")
                        ai_data = ai_analyzer.analyze_track(metrics, metadata=gpx_meta)
                        
                        made_changes = False
                        # Update fields if AI provided data
                        if ai_data.get("ai_description"):
                             # If description empty, replace. If short, append? Let's just prepend/replace if it looks better.
                             # Simple logic: if empty, set it.
                             if not track.description:
                                 track.description = ai_data["ai_description"]
                                 made_changes = True
                             elif len(track.description) < 20: # Overwrite short ones
                                 track.description = ai_data["ai_description"]
                                 made_changes = True
                        
                        if ai_data.get("ai_tags"):
                             # Merge tags
                             current_tags = []
                             if track.tags:
                                 current_tags = track.tags if isinstance(track.tags, list) else json.loads(track.tags)
                             
                             new_tags = [t for t in ai_data["ai_tags"] if t not in current_tags]
                             if new_tags:
                                 track.tags = current_tags + new_tags
                                 made_changes = True
                                 
                        if made_changes:
                            db.commit()
                            db.refresh(track)
                            print(f"Lazy Analysis applied for Track {track.id}")
                except Exception as e:
                    print(f"Lazy Analysis failed: {e}")
            # -------------------------------------------------------
            
    # Ensure JSON fields are parsed correctly (SQLite fallback)
    tags_list = []
    if track.tags:
        tags_list = track.tags if isinstance(track.tags, list) else json.loads(track.tags)
    
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "track": track,
        "tags_list": tags_list,
        "user": user,
        "track_geojson": json.dumps(track_geojson) if track_geojson else "null"
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
        "status_options": [], # [e.value for e in models.StatusEnum],
        "technicity_options": [], # [e.value for e in models.TechnicityEnum],
        "terrain_options": [] # [e.value for e in models.TerrainEnum]
    })

@app.post("/track/{track_id}/edit")
async def edit_track_action(
    track_id: int, 
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    visibility: str = Form(...),
    # status_val: str = Form(...), # Removed
    # technicity: str = Form(...), # Removed
    # terrain: str = Form(...),    # Removed
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
    # track.status = models.StatusEnum(status_val) # Removed
    # track.technicity = models.TechnicityEnum(technicity) # Removed
    # track.terrain = models.TerrainEnum(terrain) # Removed
    track.scenery_rating = scenery_rating
    track.water_points_count = water_points_count
    
    db.commit()
    
    return RedirectResponse(url=f"/track/{track_id}", status_code=303)



# --- MAP & VISUALIZATIONS ---

@app.get("/map", response_class=HTMLResponse)
async def global_map_page(request: Request, db: Session = Depends(get_db)):
    # Optional: require login
    user = await get_current_user_optional(request, db)
    has_beta = request.cookies.get("beta_access") == "granted"
    if not user and not has_beta:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
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

@app.post("/profile")
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



@app.get("/race/{race_slug}", response_class=HTMLResponse)
async def race_detail(request: Request, race_slug: str, db: Session = Depends(get_db)):
    # Fetch Event with Editions and Routes
    event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == race_slug).first()
    if not event:
        raise HTTPException(status_code=404, detail="Race Event not found")
        
    return templates.TemplateResponse("race_detail.html", {
        "request": request,
        "event": event,
        "user": await get_current_user_optional(request, db)
    })

@app.get("/superadmin", response_class=HTMLResponse)
async def super_admin_dashboard(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_super_admin)):
    
    events = db.query(models.RaceEvent).all()
    users = db.query(models.User).all()
    pending_count = db.query(models.Track).filter(models.Track.verification_status == models.VerificationStatus.PENDING).count()
    
    return templates.TemplateResponse("super_admin.html", {
        "request": request, 
        "user": current_user,
        "events": events,
        "users": users,
        "pending_count": pending_count
    })

@app.post("/superadmin/events")
async def create_event(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    website: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    
    if db.query(models.RaceEvent).filter(models.RaceEvent.slug == slug).first():
        # Ideally return error to template, for now redirect with query param or just fail
        raise HTTPException(status_code=400, detail="Slug already exists")
        
    new_event = models.RaceEvent(
        name=name,
        slug=slug,
        website=website,
        description=description
    )
    db.add(new_event)
    db.commit()
    return RedirectResponse(url="/superadmin", status_code=303)

@app.post("/superadmin/event/{event_id}/add_edition")
async def create_edition(
    event_id: int,
    request: Request,
    year: int = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    
    event = db.query(models.RaceEvent).filter(models.RaceEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Check if edition exists
    existing = db.query(models.RaceEdition).filter(models.RaceEdition.event_id == event_id, models.RaceEdition.year == year).first()
    if existing:
         pass # Duplicate, ignore or error.
    else:
        new_edition = models.RaceEdition(event_id=event_id, year=year, status=models.RaceStatus.UPCOMING)
        db.add(new_edition)
        db.commit()
        
    return RedirectResponse(url="/superadmin", status_code=303)

@app.post("/superadmin/user/{user_id}/role")
async def update_user_role(
    user_id: int,
    request: Request,
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    
    user_to_edit = db.query(models.User).filter(models.User.id == user_id).first()
    if not user_to_edit:
        raise HTTPException(status_code=404, detail="User not found")
        
    try:
         new_role = models.Role(role)
    except ValueError:
         raise HTTPException(status_code=400, detail="Invalid role")
         
    user_to_edit.role = new_role
    if new_role in [models.Role.ADMIN, models.Role.SUPER_ADMIN]:
        user_to_edit.is_admin = True
    else:
        user_to_edit.is_admin = False
        
    db.commit()
    return RedirectResponse(url="/superadmin", status_code=303)

@app.get("/superadmin/edition/{edition_id}", response_class=HTMLResponse)
async def edition_manager(edition_id: int, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_super_admin)):
    
    edition = db.query(models.RaceEdition).filter(models.RaceEdition.id == edition_id).first()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")
        
    return templates.TemplateResponse("edition_manager.html", {
        "request": request,
        "edition": edition
    })

@app.post("/superadmin/edition/{edition_id}/routes")
async def create_route(
    edition_id: int,
    request: Request,
    name: str = Form(...),
    distance_category: str = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    
    # Just create the route definition (track is pending/optional)
    new_route = models.RaceRoute(
        edition_id=edition_id,
        name=name,
        distance_category=distance_category
    )
    db.add(new_route)
    db.commit()
    return RedirectResponse(url=f"/superadmin/edition/{edition_id}", status_code=303)

@app.post("/superadmin/route/{route_id}/link_track")
async def link_track_to_route(
    route_id: int,
    request: Request,
    track_slug: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_super_admin)
):
    
    route = db.query(models.RaceRoute).filter(models.RaceRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    # Find track by slug OR ID
    track = None
    if track_slug.isdigit():
        track = db.query(models.Track).filter(models.Track.id == int(track_slug)).first()
    if not track:
        track = db.query(models.Track).filter(models.Track.slug == track_slug).first()
        
    if not track:
        # For now, just error 404. Ideally show flash message.
        raise HTTPException(status_code=404, detail="Track not found")
        
    route.official_track_id = track.id
    track.is_official_route = True
    track.verification_status = models.VerificationStatus.VERIFIED_HUMAN
    
    db.commit()
    return RedirectResponse(url=f"/superadmin/edition/{route.edition_id}", status_code=303)

@app.post("/superadmin/route/{route_id}/upload_track")
async def upload_track_to_route(
    route_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_super_admin)
):
    
    route = db.query(models.RaceRoute).filter(models.RaceRoute.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    # 1. Read & Hash
    content = await file.read()
    file_hash = calculate_file_hash(content)
    
    # 2. Check Duplicates (If exists, just link it?)
    existing_track = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
    if existing_track:
        # Link existing
        route.official_track_id = existing_track.id
        existing_track.is_official_route = True
        existing_track.verification_status = models.VerificationStatus.VERIFIED_HUMAN
        db.commit()
        return RedirectResponse(url=f"/superadmin/edition/{route.edition_id}", status_code=303)
        
    # 3. Analyze
    try:
        analytics = GpxAnalytics(content)
        metrics = analytics.calculate_metrics()
        # Basic inference
        start_lat, start_lon = metrics["start_coords"]
        
        # Save File
        upload_dir = "app/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{file_hash}.gpx")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.decode('utf-8')) # Save original or simplified? Original for official is safer.
            
        # Create Track
        new_track = models.Track(
            title=f"{route.name} - Official",
            description=f"Trace officielle pour {route.name}",
            user_id=current_admin.username, # Admin owns it
            uploader_name=current_admin.username,
            file_path=file_path,
            file_hash=file_hash,
            visibility=models.Visibility.PUBLIC,
            verification_status=models.VerificationStatus.VERIFIED_HUMAN, # Auto-verified
            is_official_route=True,
            
            distance_km=metrics["distance_km"],
            elevation_gain=metrics["elevation_gain"],
            elevation_loss=metrics["elevation_loss"],
            start_lat=start_lat,
            start_lon=start_lon
            # We can skip complex attributes for now
        )
        db.add(new_track)
        db.commit()
        db.refresh(new_track)
        
        # Link
        route.official_track_id = new_track.id
        db.commit()
        
    except Exception as e:
        print(f"Admin Upload Error: {e}")
        raise HTTPException(status_code=400, detail=f"Error processing GPX: {e}")
        
    return RedirectResponse(url=f"/superadmin/edition/{route.edition_id}", status_code=303)

from .services.race_importer import RaceImporter

@app.post("/superadmin/import_races")
async def import_races_endpoint(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(get_current_super_admin)
):
    try:
        content = await file.read()
        json_data = json.loads(content.decode('utf-8'))
        
        stats = RaceImporter.import_from_json(json_data, db)
        
        print(f"Import Stats: {stats}")
        # Optionally pass stats to template via flash message or query param
        return RedirectResponse(url="/superadmin", status_code=303)
        
    except Exception as e:
        print(f"Import Error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON or Import Error: {e}")
