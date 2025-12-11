from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, JSON, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from .database import Base

# --- Enums ---

class ActivityType(str, enum.Enum):
    TRAIL_RUNNING = "TRAIL_RUNNING"
    RUNNING = "RUNNING"
    HIKING = "HIKING"
    MTB_CROSS_COUNTRY = "MTB_CROSS_COUNTRY"
    MTB_ENDURO = "MTB_ENDURO"
    GRAVEL = "GRAVEL"
    ROAD_CYCLING = "ROAD_CYCLING"
    ALPINISM = "ALPINISM"
    SKI_TOURING = "SKI_TOURING"
    OTHER = "OTHER"

class StatusEnum(str, enum.Enum):
    TRAINING = "TRAINING"
    RACE = "RACE"

class SourceType(str, enum.Enum):
    UPLOAD = "upload"
    STRAVA_IMPORT = "strava_import"
    GARMIN_IMPORT = "garmin_import"
    MANUAL_DRAW = "manual_draw"

class Visibility(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"

class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED_ALGO = "verified_by_algo"
    VERIFIED_HUMAN = "verified_by_human"

class RouteType(str, enum.Enum):
    LOOP = "loop"
    OUT_AND_BACK = "out_and_back"
    POINT_TO_POINT = "point_to_point"

class RaceStatus(str, enum.Enum):
    UPCOMING = "UPCOMING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

# --- Models ---

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)

    # Profile
    full_name = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    location = Column(String, nullable=True) # City/Country
    website = Column(String, nullable=True)
    strava_url = Column(String, nullable=True)
    social_links = Column(JSON, nullable=True) # { "instagram": "handle", "twitter": "handle" }
    profile_picture_url = Column(String, nullable=True)

    # Community & Professional
    club_affiliation = Column(String, nullable=True) # "Team Hoka", etc.
    is_certified_guide = Column(Boolean, default=False)

    # Performance
    itra_score = Column(Integer, nullable=True)
    utmb_index = Column(Integer, nullable=True)
    betrail_score = Column(Float, nullable=True)
    favorite_activity = Column(Enum(ActivityType), nullable=True)
    achievements = Column(JSON, nullable=True) # List or Dict of manual results

    tracks = relationship("Track", back_populates="user_obj")


class Track(Base):
    __tablename__ = "tracks"

    # 1. Identity & Meta
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String, unique=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True) # Markdown
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_obj = relationship("User", back_populates="tracks")
    
    uploader_name = Column(String, default="anonymous") 

    source_type = Column(Enum(SourceType), default=SourceType.UPLOAD)
    file_path = Column(String)
    file_hash = Column(String, unique=True, index=True)
    
    visibility = Column(Enum(Visibility), default=Visibility.PUBLIC)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 2. Activity Type & Specifics
    activity_type = Column(Enum(ActivityType), default=ActivityType.TRAIL_RUNNING)
    technical_rating_context = Column(JSON, nullable=True)
    # e.g. { "mtb_scale": "S2", "alpi_grade": "AD" }

    # 3. Physical Metrics
    distance_km = Column(Float)
    elevation_gain = Column(Integer)
    elevation_loss = Column(Integer)
    
    max_altitude = Column(Integer, nullable=True)
    min_altitude = Column(Integer, nullable=True)
    avg_altitude = Column(Integer, nullable=True)
    
    max_slope = Column(Float, nullable=True)
    avg_slope_uphill = Column(Float, nullable=True)
    longest_climb = Column(Integer, nullable=True)

    # 4. Effort & Difficulty
    itra_points_estim = Column(Integer, nullable=True)
    km_effort = Column(Float, nullable=True)
    ibp_index = Column(Integer, nullable=True)
    
    # 5. Terrain & Environment
    surface_composition = Column(JSON, nullable=True) # { "asphalt": 10, "trail": 90 }
    path_type = Column(JSON, nullable=True) # { "single_track": 80 }
    
    # 6. Logistics & Conditions
    route_type = Column(Enum(RouteType), default=RouteType.LOOP)
    start_lat = Column(Float)
    start_lon = Column(Float)
    end_lat = Column(Float, nullable=True)
    end_lon = Column(Float, nullable=True)
    
    location_city = Column(String, nullable=True)
    location_region = Column(String, nullable=True)
    cities_crossed = Column(JSON, nullable=True)
    
    water_points_count = Column(Integer, default=0)
    estimated_times = Column(JSON, nullable=True)
    
    gear_requirements = Column(JSON, nullable=True) # ["Helmet", "Crampons"]
    accessibility = Column(JSON, nullable=True) # { "parking": True }
    restrictions = Column(JSON, nullable=True) # ["No Dogs"]

    # 7. Seasonal & Esthetic
    best_season = Column(JSON, nullable=True)
    scenery_rating = Column(Integer, nullable=True)
    mud_index = Column(String, nullable=True)
    exposure = Column(String, nullable=True)
    tags = Column(JSON, nullable=True)
    
    # 8. Competition Context
    is_official_route = Column(Boolean, default=False)
    
    # Links to RaceRoute if this track IS an official route
    race_route = relationship("RaceRoute", back_populates="official_track", uselist=False)


# --- Race Hierarchy ---

class RaceEvent(Base):
    """The brand / Recurring Event (e.g. 'UTMB Mont-Blanc')"""
    __tablename__ = "race_events"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    website = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    region = Column(String, nullable=True)
    circuit = Column(String, nullable=True) # "UTMB World Series", "Golden Trail"

    editions = relationship("RaceEdition", back_populates="event")


class RaceEdition(Base):
    """A specific year of the event (e.g. 'UTMB 2025')"""
    __tablename__ = "race_editions"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("race_events.id"))
    year = Column(Integer)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    status = Column(Enum(RaceStatus), default=RaceStatus.UPCOMING)

    event = relationship("RaceEvent", back_populates="editions")
    routes = relationship("RaceRoute", back_populates="edition")


class RaceRoute(Base):
    """A specific course within an edition (e.g. 'OCC' in UTMB 2025)"""
    __tablename__ = "race_routes"

    id = Column(Integer, primary_key=True, index=True)
    edition_id = Column(Integer, ForeignKey("race_editions.id"))
    
    name = Column(String) # "OCC", "CCC"
    distance_category = Column(String, nullable=True) # "50K", "100M"
    
    # Link to the GPX track that represents this route
    official_track_id = Column(Integer, ForeignKey("tracks.id"), nullable=True)
    
    results_url = Column(String, nullable=True)

    edition = relationship("RaceEdition", back_populates="routes")
    official_track = relationship("Track", back_populates="race_route")
