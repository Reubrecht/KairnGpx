import os
import json
import re
import math
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, between

from .. import models
from ..dependencies import get_db, get_current_user, get_current_user_optional, templates
from ..utils import slugify, calculate_file_hash, get_location_info
from ..services.analytics import GpxAnalytics
from ..services.ai_analyzer import AiAnalyzer
# from ..services.prediction import RaceTimePredictor # Lazy imported in detail
from ..services.prediction_config_manager import PredictionConfigManager

router = APIRouter()

@router.get("/explore", response_class=HTMLResponse)
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
    tag: Optional[str] = None,
    # Text Search (Title/Description)
    q: Optional[str] = None,
    # Scenery
    scenery_min: Optional[str] = None,
    # Pagination
    limit: int = 10
):
    try:
        from geopy.distance import geodesic

        
        user = await get_current_user_optional(request, db)
        has_beta = request.cookies.get("beta_access_v2") == "granted"
        if not user and not has_beta:
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
        query = db.query(models.Track)
        
        # 0.5 Scenery Filter
        if scenery_min and scenery_min.strip().isdigit():
             query = query.filter(models.Track.scenery_rating >= int(scenery_min))
             
        # 1. Activity Type
        if activity_type:
            query = query.filter(models.Track.activity_type == activity_type)

        # 2. Official Race
        if is_official:
            query = query.filter(models.Track.is_official_route == True)

        # 3. City/Radius Search
        current_city = city_search
        ref_lat, ref_lon = None, None
        
        # Determine Reference Location Logic
        if search_lat and search_lon:
             try:
                 ref_lat = float(search_lat)
                 ref_lon = float(search_lon)
             except:
                 pass
        elif city_search:
             # Try geocoding fallback
             try:
                 from geopy.geocoders import Nominatim
                 geolocator = Nominatim(user_agent="kairn_app")
                 location = geolocator.geocode(city_search)
                 if location:
                     ref_lat, ref_lon = location.latitude, location.longitude
             except:
                 pass
        elif user and user.location_lat and user.location_lon:
             # Fallback to User Profile Location
             ref_lat = user.location_lat
             ref_lon = user.location_lon
        
        # Apply Spatial Filter if we have a search-specific location + radius
        # (If defaulting to user location, we typically sort but maybe don't filter hard unless requested? 
        #  Current logic seems to filter IF city_search is present. Let's keep that logic.)
        if city_search:
            if ref_lat is not None and ref_lon is not None:
                # Bounding Box Filter (Approximate)
                lat_delta = radius / 111.0
                lon_delta = radius / (111.0 * abs(math.cos(math.radians(ref_lat)))) if abs(math.cos(math.radians(ref_lat))) > 0.01 else 0

                query = query.filter(
                    models.Track.start_lat.between(ref_lat - lat_delta, ref_lat + lat_delta),
                    models.Track.start_lon.between(ref_lon - lon_delta, ref_lon + lon_delta)
                )
            else:
                 # Fallback to simple string match
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
            query = query.join(models.User).filter(models.User.username.ilike(f"%{author}%"))
        
        # 7. Tags (JSON array contains)
        if tag:
            query = query.filter(models.Track.tags.ilike(f'%"{tag}"%'))
            
        # Visibility
        if user:
             query = query.filter(or_(models.Track.visibility == models.Visibility.PUBLIC, models.Track.user_id == user.id))
        else:
             query = query.filter(models.Track.visibility == models.Visibility.PUBLIC)

        tracks = query.all() # Fetch all first to sort in python (since Haversine sort in SQL is complex/expensive without PostGIS func usage)
        
        # 7.5. Text Search (Python Side)
        if q:
            q_norm = slugify(q)
            text_filtered = []
            for t in tracks:
                t_title_norm = slugify(t.title) if t.title else ""
                t_desc_norm = slugify(t.description) if t.description else ""
                if q_norm in t_title_norm or q_norm in t_desc_norm:
                    text_filtered.append(t)
            tracks = text_filtered
        
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

        # --- SORTING BY DISTANCE ---
        if ref_lat is not None and ref_lon is not None:
            def get_dist(t):
                if t.start_lat and t.start_lon:
                    return geodesic((ref_lat, ref_lon), (t.start_lat, t.start_lon)).km
                return 999999 # Far away if no coords
            
            tracks.sort(key=get_dist)
        else:
            # Fallback sort by date
            tracks.sort(key=lambda x: x.created_at, reverse=True)

        # --- PAGINATION / LIMIT ---
        total_tracks_count = len(tracks)
        tracks = tracks[:limit]

        # 9. FETCH PENDING OFFICIAL RACES
        # ONLY if not searching for specific author and typically we might want to show them if they match location
        grouped_events = {}
        if not author: 
            pending_query = db.query(models.RaceRoute).filter(models.RaceRoute.official_track_id == None)\
                .join(models.RaceEdition).join(models.RaceEvent)

            if city_search:
                 pending_query = pending_query.filter(models.RaceEvent.region.ilike(f"%{city_search}%"))
            
            pending_routes = pending_query.all()
            
            # Group Hierarchy: Continent > Department > Country > Region > Massif > City > Event
            # Actually user asked: continent, departement, pays, region, massif, ville, lieu de départ
            
            # Helper to organize
            hierarchy = {} 

            for pr in pending_routes:
                event = pr.edition.event
                edition = pr.edition
                
                # Check filters for route
                p_dist = 0
                p_elev = 0
                m_dist = re.search(r'(\d+)\s*km', pr.name, re.IGNORECASE)
                if m_dist: p_dist = int(m_dist.group(1))
                m_elev = re.search(r'(\d+)\s*m', pr.name, re.IGNORECASE)
                if m_elev: p_elev = int(m_elev.group(1))

                match_filters = True
                if min_dist is not None and p_dist < min_dist: match_filters = False
                if max_dist is not None and p_dist > max_dist: match_filters = False
                if min_elev is not None and p_elev < min_elev: match_filters = False
                if max_elev is not None and p_elev > max_elev: match_filters = False
                
                if not match_filters:
                     continue

                # Build Event Structure if not exists
                ev_key = f"event_{event.id}"
                
                # We need to inject this event into the hierarchy
                # Creating a structure:
                # hierarchy = {
                #   "Europe": {
                #       "France": { ... }
                #   }
                # }
                # Using a flat dict of paths might be easier for template? Or recursive dict.
                # Let's try recursive dict construction.
                
                keys = [
                    event.continent or "Autre Continent",
                    event.country or "Autre Pays", # Swapped per user request "departement" before pays? usually Country > Dept. User said: continent, departement, pays. Weird order. Let's stick to logical: Continent > Country > Region/Dept > Massif > City
                    # User request: continent, departement, pays, region, massif, ville, lieu de départ
                    # Let's follow user exact order or logical fallback? "departement" is usually inside "pays".
                    # Let's try: Continent -> Pays -> Departement -> Region -> Massif -> Ville
                    event.department or "Autre Département",
                    event.region or "Autre Région",
                    event.massif or "Autre Massif",
                    event.city or "Autre Ville"
                ]
                
                current_level = hierarchy
                for k in keys:
                    if k not in current_level:
                        current_level[k] = {}
                    current_level = current_level[k]
                
                # Now at the leaf (Ville), we store the events list
                if "_events" not in current_level:
                    current_level["_events"] = {}
                
                if ev_key not in current_level["_events"]:
                     current_level["_events"][ev_key] = {
                        "id": ev_key,
                        "slug": event.slug,
                        "title": f"{event.name} {edition.year}",
                        "location_city": event.city or event.region,
                        "routes": [],
                        "is_grouped_event": True,
                        "map_thumbnail_url": None
                     }
                
                current_level["_events"][ev_key]["routes"].append({
                     "id": pr.id,
                     "name": pr.name,
                     "distance_km": p_dist,
                     "elevation_gain": p_elev
                })

            grouped_events = hierarchy

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
        
        # Count actual tracks (excluding grouped events - handled separately now)
        # real_track_count = total_tracks_count # Just tracks
        
        # 11. Prepare Map Data (JSON)
        map_tracks_data = [{"id": str(t.id)} for t in tracks]
        map_tracks_json = json.dumps(map_tracks_data)

        return templates.TemplateResponse("index.html", {
            "request": request,
            "tracks": tracks, 
            "grouped_events_hierarchy": grouped_events,
            "map_tracks_json": map_tracks_json,
            "real_track_count": total_tracks_count,
            "user": user,
            "active_page": "explore",
            "current_city": current_city,
            "radius": radius,
            "all_tags": sorted_tags,
            "current_tag": tag,
            "limit": limit, # Pagination
            "has_more_tracks": total_tracks_count > limit
        })
    except Exception as e:
        import traceback
        import sys
        error_msg = f"\n{'='*80}\nEXPLORE ENDPOINT ERROR\n{'='*80}\n{str(e)}\n{traceback.format_exc()}\n{'='*80}\n"
        print(error_msg, file=sys.stderr, flush=True)
        try:
            log_path = os.path.join(os.path.dirname(__file__), "..", "..", "kairn_error.log")
            with open(log_path, "a") as f:
                f.write(error_msg)
        except:
            pass
        raise e

@router.get("/search", response_class=HTMLResponse)
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
        query = query.filter(or_(
            models.Track.location_city.ilike(f"%{location}%"),
            models.Track.location_region.ilike(f"%{location}%"),
            models.Track.title.ilike(f"%{location}%") 
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
        query = query.join(models.User).filter(models.User.username.ilike(f"%{author}%"))

    # Visibility
    if user:
         query = query.filter(or_(models.Track.visibility == models.Visibility.PUBLIC, models.Track.user_id == user.id))
    else:
         query = query.filter(models.Track.visibility == models.Visibility.PUBLIC)

    tracks = query.order_by(models.Track.created_at.desc()).all()

    # 7. Post-Processing for Ratio D+
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

    return templates.TemplateResponse("search.html", {
        "request": request,
        "tracks": tracks,
        "user": user,
    })

@router.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request, db: Session = Depends(get_db), race_route_id: Optional[int] = None):
    user = await get_current_user(request, db) # Force login
    
    prefill_race = None
    if race_route_id:
        route = db.query(models.RaceRoute).filter(models.RaceRoute.id == race_route_id).first()
        if route:
            prefill_race = {
                "id": route.id,
                "name": route.edition.event.name,
                "year": route.edition.year,
                "route_name": route.name,
                "category": route.distance_category
            }

    race_events = db.query(models.RaceEvent).order_by(models.RaceEvent.name).all()

    return templates.TemplateResponse("upload.html", {
        "request": request,
        "status_options": [],
        "technicity_options": [],
        "terrain_options": [],
        "user": user,
        "prefill_race": prefill_race,
        "race_events": race_events
    })

@router.post("/upload")
async def upload_track(
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    environment: List[str] = Form([]),
    visibility: str = Form("public"),
    activity_type: str = Form("TRAIL_RUNNING"),
    tags: str = Form(None), 
    water_points_count: int = Form(0),
    scenery_rating: int = Form(None),
    
    # Official Race Fields
    is_official_bot: bool = Form(False),
    linked_race_route_id: Optional[int] = Form(None),
    race_name: Optional[str] = Form(None),
    race_year: Optional[int] = Form(None),
    race_route_name: Optional[str] = Form(None),
    
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    content = await file.read()
    file_hash = calculate_file_hash(content)

    existing_track = db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
    if existing_track:
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "error": f"Cette trace existe déjà : '{existing_track.title}' (importée le {existing_track.created_at.strftime('%d/%m/%Y')})",
            "user": current_user,
            "status_options": [],
            "technicity_options": [],
            "terrain_options": []
        })

    analytics = GpxAnalytics(content)
    metrics = analytics.calculate_metrics()
    inferred = analytics.infer_attributes(metrics)
    gpx_meta = analytics.get_metadata()
    
    if gpx_meta.get("name") and (title.lower().endswith(".gpx") or title == "Trace"):
        title = gpx_meta["name"]
        
    if not description and gpx_meta.get("description"):
        description = gpx_meta["description"]
        
    if gpx_meta.get("keywords"):
        kws = gpx_meta["keywords"]
        if isinstance(kws, str):
            inferred["tags"].extend([k.strip() for k in kws.split(",") if k.strip()])
        elif isinstance(kws, list):
             inferred["tags"].extend(kws)
    
    if not metrics:
         raise HTTPException(status_code=400, detail="Could not parse or analyze GPX file.")

    try:
        ai_analyzer = AiAnalyzer()
        if ai_analyzer.model:
            print("Calling Gemini for analysis...")
            
            user_tags_list = []
            if tags:
                user_tags_list = [t.strip() for t in tags.split(",") if t.strip()]

            ai_data = ai_analyzer.analyze_track(
                metrics, 
                metadata=gpx_meta, 
                user_title=title, 
                user_description=description, 
                is_race=is_official_bot,
                scenery_rating=scenery_rating,
                water_count=water_points_count,
                user_tags=user_tags_list
            )
            
            if ai_data.get("ai_description"):
                description = ai_data["ai_description"]
            
            if ai_data.get("ai_title"):
                title = ai_data["ai_title"]
                
            if ai_data.get("ai_tags"):
                inferred["tags"].extend(ai_data["ai_tags"])
                
    except Exception as e:
        print(f"AI Integration skipped: {e}")

    start_lat, start_lon = metrics["start_coords"]
    city, region, country = get_location_info(start_lat, start_lon)
    
    simplified_xml = analytics.simplify_track(epsilon=0.00005)
    
    upload_dir = "app/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{file_hash}.gpx")
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(simplified_xml if simplified_xml else content.decode('utf-8'))

    race_route_obj = None
    is_official = False
    
    if is_official_bot and race_name and race_year:
        try:
            is_official = True
            event_slug = slugify(race_name)
            event = db.query(models.RaceEvent).filter(models.RaceEvent.slug == event_slug).first()
            if not event:
                event = models.RaceEvent(name=race_name, slug=event_slug)
                db.add(event)
                db.commit()
                db.refresh(event)
            
            edition = db.query(models.RaceEdition).filter(models.RaceEdition.event_id == event.id, models.RaceEdition.year == race_year).first()
            if not edition:
                edition = models.RaceEdition(event_id=event.id, year=race_year)
                db.add(edition)
                db.commit()
                db.refresh(edition)
        except Exception as e:
            print(f"Race logic error: {e}")

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
        user_id=current_user.id,
        activity_type=models.ActivityType(activity_type),
        is_official_route=is_official,
        distance_km=metrics["distance_km"],
        elevation_gain=metrics["elevation_gain"],
        elevation_loss=metrics["elevation_loss"],
        max_altitude=metrics["max_altitude"],
        min_altitude=metrics["min_altitude"],
        avg_altitude=metrics["avg_altitude"],
        max_slope=metrics["max_slope"],
        avg_slope_uphill=metrics["avg_slope_uphill"],
        km_effort=metrics["km_effort"],
        itra_points_estim=metrics["itra_points_estim"],
        ibp_index=metrics.get("ibp_index"),
        longest_climb=metrics.get("longest_climb"),
        route_type=metrics["route_type"],
        start_lat=start_lat,
        start_lon=start_lon,
        end_lat=metrics["end_coords"][0],
        end_lon=metrics["end_coords"][1],
        location_city=city,
        location_region=region,
        location_country=country,
        estimated_times=metrics["estimated_times"],
        file_path=file_path,
        file_hash=file_hash,
        visibility=models.Visibility(visibility),
        water_points_count=water_points_count,
        scenery_rating=scenery_rating,
        technicity_score=None, 
        environment=environment,
        tags=[t.strip() for t in tags.split(',')] if tags else []
    )
    
    db.add(new_track)
    db.commit()
    db.refresh(new_track)
    
    if is_official and 'edition' in locals():
        try:
            new_race_route = models.RaceRoute(
                edition_id=edition.id,
                name=race_route_name or title, 
                official_track_id=new_track.id
            )
            db.add(new_race_route)
            db.commit()
        except Exception as e:
            print(f"Failed to create RaceRoute: {e}")

    if linked_race_route_id:
        race_route = db.query(models.RaceRoute).filter(models.RaceRoute.id == linked_race_route_id).first()
        if race_route:
            print(f"Linking Track {new_track.id} to Official Route {race_route.name}")
            race_route.official_track_id = new_track.id
            new_track.is_official_route = True
            new_track.status = models.StatusEnum.RACE
            new_track.verification_status = models.VerificationStatus.PENDING
            db.commit()
            db.commit() # ?

    return RedirectResponse(url=f"/track/{new_track.id}", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/track/{track_identifier}", response_class=HTMLResponse)
async def track_detail(track_identifier: str, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    has_beta = request.cookies.get("beta_access_v2") == "granted"
    if not user and not has_beta:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    track = None
    if track_identifier.isdigit():
        track = db.query(models.Track).filter(models.Track.id == int(track_identifier)).first()
    
    if not track:
        track = db.query(models.Track).filter(models.Track.slug == track_identifier).first()

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    # Generate GeoJSON for MapLibre
    track_geojson = None
    if os.path.exists(track.file_path):
        with open(track.file_path, "r", encoding="utf-8") as f:
            content = f.read()
            analytics = GpxAnalytics(content)
            track_geojson = analytics.get_geojson()
            
            # --- Lazy AI Analysis ---
            has_tags = track.tags and (isinstance(track.tags, list) and len(track.tags) > 0)
            needs_analysis = not has_tags or not track.description or len(track.description) < 20
            
            if needs_analysis:
                try:
                    metrics = analytics.calculate_metrics()
                    gpx_meta = analytics.get_metadata()
                    
                    ai_analyzer = AiAnalyzer()
                    if ai_analyzer.model:
                        print(f"Lazy Analysis triggered for Track {track.id}...")
                        ai_data = ai_analyzer.analyze_track(metrics, metadata=gpx_meta)
                        
                        made_changes = False
                        if ai_data.get("ai_description"):
                             if not track.description:
                                 track.description = ai_data["ai_description"]
                                 made_changes = True
                             elif len(track.description) < 20: 
                                 track.description = ai_data["ai_description"]
                                 made_changes = True
                        
                        if ai_data.get("ai_tags"):
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
            
    tags_list = []
    if track.tags:
        tags_list = track.tags if isinstance(track.tags, list) else json.loads(track.tags)
    
    user_prediction = None
    if user:
        try:
            from ..services.prediction import RaceTimePredictor
            user_prediction = RaceTimePredictor.predict(track, user)
        except Exception as e:
            print(f"Prediction Error: {e}")
            
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "track": track,
        "tags_list": tags_list,
        "user": user,
        "track_geojson": json.dumps(track_geojson) if track_geojson else "null",
        "user_prediction": user_prediction
    })

@router.get("/raw_gpx/{track_id}")
def get_raw_gpx(track_id: int, db: Session = Depends(get_db)):
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    safe_path = os.path.join("app/uploads", f"{track.file_hash}.gpx")
    
    if not os.path.exists(safe_path):
        if os.path.exists(track.file_path):
             safe_path = track.file_path
        else:
             print(f"File missing: {safe_path} (Hash: {track.file_hash})")
             raise HTTPException(status_code=404, detail="GPX File not found on server")
    
    with open(safe_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content=content, media_type="application/gpx+xml")

@router.get("/track/{track_id}/edit", response_class=HTMLResponse)
async def edit_track_form(track_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
        
    if track.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    races_raw = db.query(models.RaceEvent).all()
    races_data = []
    for r in races_raw:
        editions_data = []
        for e in sorted(r.editions, key=lambda x: x.year, reverse=True):
            routes_data = [{"id": ro.id, "name": ro.name} for ro in e.routes]
            editions_data.append({"id": e.id, "year": e.year, "routes": routes_data})
        races_data.append({"id": r.id, "name": r.name, "editions": editions_data})
    
    races_json = json.dumps(races_data)
    
    return templates.TemplateResponse("edit_track.html", {
        "request": request,
        "track": track,
        "user": user,
        "races": races_raw, 
        "races_json": races_json, 
        "activity_options": [e.value for e in models.ActivityType],
        "technicity_options": [], 
        "terrain_options": [] 
    })

@router.post("/track/{track_id}/edit")
async def edit_track_action(
    track_id: int, 
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    visibility: str = Form(...),
    scenery_rating: int = Form(None),
    water_points_count: int = Form(0),
    technicity_score: float = Form(None),
    race_route_id: int = Form(None),
    activity_type: str = Form(...),
    environment: List[str] = Form([]),
    tags: str = Form(None),
    db: Session = Depends(get_db)
):
    user = await get_current_user(request, db)
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
        
    if track.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    track.title = title
    track.description = description
    track.visibility = models.Visibility(visibility)
    
    try:
        track.activity_type = models.ActivityType(activity_type)
    except ValueError:
        pass

    track.scenery_rating = scenery_rating
    track.water_points_count = water_points_count
    track.technicity_score = technicity_score

    if race_route_id:
        route = db.query(models.RaceRoute).filter(models.RaceRoute.id == race_route_id).first()
        if route:
            route.official_track_id = track.id
            track.is_official_route = True
            if not track.title:
                 track.title = f"{route.edition.event.name} - {route.name}"
    
    track.environment = environment
    track.tags = [t.strip() for t in tags.split(',')] if tags else []
    
    db.commit()
    
    return RedirectResponse(url=f"/track/{track_id}", status_code=303)

@router.post("/track/{track_id}/analyze")
async def analyze_track_action(track_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    
    # Check permissions (Admin only as per UI)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Re-run Analysis
    try:
        if os.path.exists(track.file_path):
            with open(track.file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            analytics = GpxAnalytics(content)
            metrics = analytics.calculate_metrics()
            gpx_meta = analytics.get_metadata()
            
            ai_analyzer = AiAnalyzer()
            if ai_analyzer.model:
                print(f"Manual AI Re-analysis triggered for Track {track.id}...")
                
                # We pass existing values to prioritize them if AI fails or returns empty, 
                # but the AI analyzer typically overrides if it finds something better locally 
                # or we can force it. For now let's just use the standard flow.
                
                # Get current tags
                current_tags = []
                if track.tags:
                    current_tags = track.tags if isinstance(track.tags, list) else json.loads(track.tags)
                
                ai_data = ai_analyzer.analyze_track(
                    metrics, 
                    metadata=gpx_meta,
                    user_title=track.title,
                    user_description=track.description,
                    scenery_rating=track.scenery_rating,
                    water_count=track.water_points_count,
                    user_tags=current_tags
                )
                
                # Apply updates
                if ai_data.get("ai_description"):
                    track.description = ai_data["ai_description"]
                
                if ai_data.get("ai_title"):
                    track.title = ai_data["ai_title"]
                    
                if ai_data.get("ai_tags"):
                    # Merge tags unique
                    new_tags = [t for t in ai_data["ai_tags"] if t not in current_tags]
                    if new_tags:
                        track.tags = current_tags + new_tags
                
                # Also update Verification Status if it was pending
                if track.verification_status == models.VerificationStatus.PENDING:
                     track.verification_status = models.VerificationStatus.VERIFIED_BY_ALGO

                db.commit()
                print(f"AI Re-analysis completed for Track {track.id}")
                
            else:
                 print("AI Model not available.")
        else:
             print("Track file not found.")
             
    except Exception as e:
        print(f"AI Re-analysis failed: {e}")
        # Optionally flash an error message using session or similar if available, 
        # but for now we just log it.

    return RedirectResponse(url=f"/track/{track_id}/edit", status_code=303)

@router.post("/track/{track_id}/delete")
async def delete_track_action(track_id: int, request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    track = db.query(models.Track).filter(models.Track.id == track_id).first()
    
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
        
    if track.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    try:
        safe_path = os.path.join("app/uploads", f"{track.file_hash}.gpx")
        if os.path.exists(safe_path):
            os.remove(safe_path)
    except Exception as e:
        print(f"Error deleting file: {e}")

    db.delete(track)
    db.commit()
    
    referer = request.headers.get("referer", "/profile")
    return RedirectResponse(url=referer, status_code=303)

@router.get("/map", response_class=HTMLResponse)
async def global_map_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user_optional(request, db)
    has_beta = request.cookies.get("beta_access") == "granted"
    if not user and not has_beta:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    tracks = db.query(models.Track).filter(models.Track.visibility == models.Visibility.PUBLIC).all()
    users_with_location = db.query(models.User).filter(models.User.location_lat.isnot(None), models.User.location_lon.isnot(None)).all()
    
    # Prepare JSON data for the map to avoid Jinja in JS errors
    tracks_data = []
    for t in tracks:
        tracks_data.append({
            "id": t.id,
            "title": t.title,
            "start_lat": t.start_lat,
            "start_lon": t.start_lon,
            "distance_km": t.distance_km,
            "elevation_gain": t.elevation_gain
        })
    
    users_data = []
    for u in users_with_location:
         users_data.append({
             "username": u.username,
             "location_lat": u.location_lat,
             "location_lon": u.location_lon,
             "location_city": u.location_city,
             "profile_picture": u.profile_picture if u.profile_picture else None 
         })

    import json
    return templates.TemplateResponse("heatmap.html", {
        "request": request,
        "tracks": tracks, # Keep raw for count or other uses if needed
        "tracks_json": json.dumps(tracks_data),
        "users_json": json.dumps(users_data),
        "total_tracks": len(tracks),
        "user": user
    })
