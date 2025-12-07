import hashlib
import os
import shutil
from typing import List, Optional

from fastapi import FastAPI, Depends, Request, UploadFile, File, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import between, or_
from sqlalchemy.orm import Session
from geopy.geocoders import Nominatim
import gpxpy
import gpxpy.gpx

from . import models, database

# Create tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Kairn Trail Platform")

# Mount static files
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

# Helpers
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

# Routes

@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    technicity: Optional[str] = None,
    city_search: Optional[str] = None,
    is_high_mountain: Optional[bool] = None
):
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
        "technicity_options": technicity_options
    })

@app.get("/upload", response_class=HTMLResponse)
def upload_form(request: Request):
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "status_options": [e.value for e in models.StatusEnum],
        "technicity_options": [e.value for e in models.TechnicityEnum],
        "terrain_options": [e.value for e in models.TerrainEnum]
    })

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
    db: Session = Depends(get_db)
):
    # 1. Read file and calculate hash
    content = await file.read()
    file_hash = calculate_file_hash(content)

    # 2. Check strict duplicate (Hash)
    existing_track = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
    if existing_track:
        raise HTTPException(status_code=409, detail="This GPX file has already been uploaded.")

    # 3. Parse GPX
    try:
        gpx = gpxpy.parse(content)
        if not gpx.tracks:
             raise ValueError("No tracks found in GPX")
        
        # Basic stats
        distance_2d = gpx.length_2d()
        distance_km = round(distance_2d / 1000, 2)
        
        uphill, downhill = gpx.get_uphill_downhill()
        elevation_gain = int(uphill)
        elevation_loss = int(downhill)

        # Start point
        start_point = gpx.tracks[0].segments[0].points[0]
        start_lat = start_point.latitude
        start_lon = start_point.longitude

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX file: {str(e)}")

    # 4. Check geometric duplicate
    # Logic: Same distance +/- 5% AND Same start point within ~200m (approx 0.002 degrees)
    # This is a basic approximation for speed.
    
    dist_min = distance_km * 0.95
    dist_max = distance_km * 1.05
    lat_min = start_lat - 0.002
    lat_max = start_lat + 0.002
    lon_min = start_lon - 0.002
    lon_max = start_lon + 0.002

    potential_duplicate = db.query(models.Track).filter(
        between(models.Track.distance_km, dist_min, dist_max),
        between(models.Track.start_lat, lat_min, lat_max),
        between(models.Track.start_lon, lon_min, lon_max)
    ).first()

    warning_msg = None
    if potential_duplicate:
        warning_msg = f"Warning: Similar track found (ID: {potential_duplicate.id}, {potential_duplicate.title})."

    # 5. Geocoding
    city, region = get_location_info(start_lat, start_lon)

    # 6. Save file to disk
    upload_dir = "app/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}.gpx")
    
    # Write the content we already read (pointer is at end, need to reset if we were using file object, but we have content bytes)
    with open(file_path, "wb") as f:
        f.write(content)

    # 7. Save to DB
    new_track = models.Track(
        title=title,
        description=description,
        distance_km=distance_km,
        elevation_gain=elevation_gain,
        elevation_loss=elevation_loss,
        file_path=file_path,
        file_hash=file_hash,
        start_lat=start_lat,
        start_lon=start_lon,
        location_city=city,
        location_region=region,
        status=models.StatusEnum(status_val),
        technicity=models.TechnicityEnum(technicity),
        terrain=models.TerrainEnum(terrain),
        is_high_mountain=is_high_mountain,
        is_coastal=is_coastal,
        is_forest=is_forest,
        is_urban=is_urban,
        is_desert=is_desert
    )
    
    db.add(new_track)
    db.commit()
    db.refresh(new_track)

    # Allow redirecting with a success message or similar? For MVP, just redirect to detail.
    return RedirectResponse(url=f"/track/{new_track.id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/track/{track_id}", response_class=HTMLResponse)
def track_detail(track_id: int, request: Request, db: Session = Depends(get_db)):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    # Read GPX content to pass to frontend for mapping if needed, 
    # OR serve the file statically. Let's serve the file statically via an endpoint or direct link if in static.
    # But files are in /app/uploads, not static. We should expose a route to get raw GPX or duplicate to static.
    # Better: simple route to serve raw GPX.
    
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "track": track
    })

@app.get("/raw_gpx/{track_id}")
def get_raw_gpx(track_id: int, db: Session = Depends(get_db)):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track or not os.path.exists(track.file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    with open(track.file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return content

