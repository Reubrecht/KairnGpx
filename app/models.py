from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, JSON, Text, ForeignKey, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from .database import Base

# Enums
class StatusEnum(str, enum.Enum):
    TRAINING = "TRAINING"
    OFFICIAL_RACE = "OFFICIAL_RACE"

class TechnicityEnum(str, enum.Enum):
    ROULANT = "ROULANT"
    PEU_TECHNIQUE = "PEU_TECHNIQUE"
    TECHNIQUE = "TECHNIQUE"
    TRES_TECHNIQUE = "TRES_TECHNIQUE"
    AERIEN = "AERIEN"

class TerrainEnum(str, enum.Enum):
    TERRE = "TERRE"
    ROCHER = "ROCHER"
    BOUE = "BOUE"
    NEIGE = "NEIGE"
    SABLE = "SABLE"
    MIXTE = "MIXTE"

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

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False)

class Track(Base):
    __tablename__ = "tracks"

    # 1. Identity & Meta
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String, unique=True, index=True)
    title = Column(String, index=True)
    description = Column(Text, nullable=True) # Text for Markdown/HTML
    user_id = Column(String, default="anonymous", index=True)
    
    source_type = Column(Enum(SourceType), default=SourceType.UPLOAD)
    file_path = Column(String) # Raw GPX
    file_hash = Column(String, unique=True, index=True)
    
    visibility = Column(Enum(Visibility), default=Visibility.PUBLIC)
    verification_status = Column(Enum(VerificationStatus), default=VerificationStatus.PENDING)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 2. Physical Metrics (Calculated)
    distance_km = Column(Float)
    elevation_gain = Column(Integer)
    elevation_loss = Column(Integer)
    
    max_altitude = Column(Integer, nullable=True)
    min_altitude = Column(Integer, nullable=True)
    avg_altitude = Column(Integer, nullable=True)
    
    max_slope = Column(Float, nullable=True) # Percentage
    avg_slope_uphill = Column(Float, nullable=True) # Percentage
    longest_climb = Column(Integer, nullable=True) # Vertical gain of longest continuous climb

    # 3. Effort & Difficulty
    itra_points_estim = Column(Integer, nullable=True)
    km_effort = Column(Float, nullable=True)
    ibp_index = Column(Integer, nullable=True)
    
    technicity = Column(Enum(TechnicityEnum), default=TechnicityEnum.PEU_TECHNIQUE)
    # Endurance scale could be calculated or Enum, keeping simple for now
    endurance_scale = Column(Integer, nullable=True) # 1-5 or similar

    # 4. Terrain & Surface (JSON Analysis)
    surface_composition = Column(JSON, nullable=True) # { "asphalt": 10, "trail": 90 }
    path_type = Column(JSON, nullable=True) # { "single_track": 80, "road": 20 }

    # 5. Logistics
    route_type = Column(Enum(RouteType), default=RouteType.LOOP)
    
    start_lat = Column(Float)
    start_lon = Column(Float)
    end_lat = Column(Float, nullable=True)
    end_lon = Column(Float, nullable=True)
    
    location_city = Column(String, nullable=True)
    location_region = Column(String, nullable=True)
    cities_crossed = Column(JSON, nullable=True) # List of strings
    
    water_points_count = Column(Integer, default=0)
    
    estimated_times = Column(JSON, nullable=True) # { "hiker": "4h30", "runner": "2h15" }

    # 6. Seasonal & Esthetic
    best_season = Column(JSON, nullable=True) # ["Spring", "Summer"]
    scenery_rating = Column(Integer, nullable=True) # 1-5
    mud_index = Column(String, nullable=True) # Enum stored as string for flexibility
    exposure = Column(String, nullable=True) # Enum stored as string
    tags = Column(JSON, nullable=True) # ["Cascade", "Sommet"]

    # Legacy fields mapping (kept for compatibility or refactored)
    status = Column(Enum(StatusEnum), default=StatusEnum.TRAINING)
    terrain = Column(Enum(TerrainEnum), default=TerrainEnum.MIXTE)
    
    # Booleans mapped to tags or kept
    is_high_mountain = Column(Boolean, default=False)
    is_coastal = Column(Boolean, default=False)
    is_forest = Column(Boolean, default=False)
    is_urban = Column(Boolean, default=False)
    is_desert = Column(Boolean, default=False)

    # 7. Official Race Link
    race_id = Column(Integer, ForeignKey("official_races.id"), nullable=True)
    race_year = Column(Integer, nullable=True)
    race_category = Column(String, nullable=True) # "42km", "Ultra"
    
    race = relationship("OfficialRace", back_populates="tracks")

class OfficialRace(Base):
    __tablename__ = "official_races"
    
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    website = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    
    tracks = relationship("Track", back_populates="race")
