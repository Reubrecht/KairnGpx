import os
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app import models
from app.utils import slugify, calculate_file_hash, get_location_info
from app.services.analytics import GpxAnalytics
from app.services.ai_analyzer import AiAnalyzer

class UnifiedEventService:
    def __init__(self, db: Session, user: models.User):
        self.db = db
        self.user = user

    async def create_event_hierarchy(
        self, 
        event_name: str, 
        year: int, 
        route_name: str, 
        gpx_content: bytes = None,
        event_slug: str = None,
        distance_category: str = None
    ):
        """
        Creates or retrieves Event -> Edition -> Route and links a Track from the GPX content.
        All in one transaction flow (though caller should handle commit if preferred, here we commit step by step or bulk).
        We will rely on the caller to commit usually, but here we might need to flush to get IDs.
        """
        
        # 1. Event
        if not event_slug:
            event_slug = slugify(event_name)
            
        # Try to find by slug first
        event = self.db.query(models.RaceEvent).filter(models.RaceEvent.slug == event_slug).first()
        if not event:
            # Create new event
            event = models.RaceEvent(
                name=event_name, 
                slug=event_slug
            )
            # Add current user as owner
            event.owners.append(self.user)
            self.db.add(event)
            self.db.flush() # Need ID for edition
            
        # 2. Edition
        edition = self.db.query(models.RaceEdition).filter_by(event_id=event.id, year=year).first()
        if not edition:
            edition = models.RaceEdition(
                event_id=event.id, 
                year=year,
                status=models.RaceStatus.UPCOMING
            )
            self.db.add(edition)
            self.db.flush() # Need ID for route
            
        # 3. Track Processing (Reuse logic similar to tracks.py upload)
        track = None
        if gpx_content:
            file_hash = calculate_file_hash(gpx_content)
            track = self.db.query(models.Track).filter(models.Track.file_hash == file_hash).first()
            
            if not track:
                # Parse GPX
                analytics = GpxAnalytics(gpx_content)
                metrics = analytics.calculate_metrics()
                
                if not metrics:
                    raise ValueError("Impossible d'analyser le fichier GPX.")

                # Save File
                filename = f"{file_hash}.gpx"
                upload_dir = "app/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                
                # Write file if not exists
                if not os.path.exists(file_path):
                    with open(file_path, "wb") as f:
                        f.write(gpx_content)
                
                # Location Info
                start_lat, start_lon = metrics["start_coords"]
                city, region, country = get_location_info(start_lat, start_lon)
                
                # Tags / AI Inference
                # inferred = analytics.infer_attributes(metrics)

                # Create Track
                track_slug = slugify(f"{event.name} {year} {route_name}")
                # Ensure unique slug
                counter = 1
                base_slug = track_slug
                while self.db.query(models.Track).filter(models.Track.slug == track_slug).first():
                    track_slug = f"{base_slug}-{counter}"
                    counter += 1

                track = models.Track(
                    title=f"{event.name} {year} - {route_name}",
                    slug=track_slug,
                    description=f"Trace officielle pour {route_name} ({year})",
                    uploader_name=self.user.username,
                    user_id=self.user.id,
                    file_hash=file_hash,
                    file_path=file_path,
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
                    route_type=metrics["route_type"],
                    
                    start_lat=start_lat,
                    start_lon=start_lon,
                    end_lat=metrics["end_coords"][0],
                    end_lon=metrics["end_coords"][1],
                    location_city=city,
                    location_region=region,
                    location_country=country,
                    
                    estimated_times=metrics["estimated_times"],
                    
                    activity_type=models.ActivityType.TRAIL_RUNNING, 
                    visibility=models.Visibility.PUBLIC,
                    is_official_route=True,
                    verification_status=models.VerificationStatus.VERIFIED_HUMAN
                )
                self.db.add(track)
                self.db.flush()
            else:
                # If track exists, ensure it is marked as official
                track.is_official_route = True
                if not track.is_official_route: # Update if changed
                    self.db.add(track)

        # 4. Route
        route = self.db.query(models.RaceRoute).filter_by(edition_id=edition.id, name=route_name).first()
        if not route:
            route = models.RaceRoute(
                edition_id=edition.id,
                name=route_name,
                distance_km=track.distance_km if track else None,
                elevation_gain=track.elevation_gain if track else None,
                distance_category=distance_category,
                official_track_id=track.id if track else None
            )
            # If track exists, sync metrics
            if track:
                 route.distance_km = track.distance_km
                 route.elevation_gain = track.elevation_gain

            self.db.add(route)
        else:
            # Update existing route link
            if track:
                route.official_track_id = track.id
                # Update metrics from track if route ones are missing
                if not route.distance_km:
                    route.distance_km = track.distance_km
                if not route.elevation_gain:
                    route.elevation_gain = track.elevation_gain
            self.db.add(route)
            
        self.db.commit()
        
        return {
            "event": event,
            "edition": edition,
            "route": route,
            "track": track
        }
