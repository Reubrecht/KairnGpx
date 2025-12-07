from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum
from sqlalchemy.sql import func
import enum
from .database import Base

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

class Track(Base):
    __tablename__ = "tracks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    user_id = Column(String, default="anonymous") # Placeholder for auth if needed later

    # Physical stats
    distance_km = Column(Float)
    elevation_gain = Column(Integer)
    elevation_loss = Column(Integer)

    # File info
    file_path = Column(String)
    file_hash = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Location
    start_lat = Column(Float)
    start_lon = Column(Float)
    location_city = Column(String, nullable=True)
    location_region = Column(String, nullable=True)

    # Categorization
    status = Column(Enum(StatusEnum), default=StatusEnum.TRAINING)
    technicity = Column(Enum(TechnicityEnum), default=TechnicityEnum.PEU_TECHNIQUE)
    terrain = Column(Enum(TerrainEnum), default=TerrainEnum.MIXTE)

    # Environment Tags
    is_high_mountain = Column(Boolean, default=False)
    is_coastal = Column(Boolean, default=False)
    is_forest = Column(Boolean, default=False)
    is_urban = Column(Boolean, default=False)
    is_desert = Column(Boolean, default=False)
