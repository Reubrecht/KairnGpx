from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from .. import models
from ..dependencies import get_db, get_current_user
from ..services.analytics import GpxAnalytics
from ..services.strategy_calculator import StrategyCalculator

import os

router = APIRouter(
    prefix="/api/strategy",
    tags=["strategy"]
)

# --- Pydantic Models ---
class Waypoint(BaseModel):
    km: float
    name: str
    type: str = "ravito"

class CalculationRequest(BaseModel):
    track_id: int
    target_time_minutes: int
    start_time_hour: float = 6.0
    waypoints: List[Waypoint]
    fatigue_factor: float = 1.0
    technicity_score: float = 1.0
    nutrition_strategy: Optional[str] = None

class StrategySaveRequest(CalculationRequest):
    title: str
    pacing_method: str = "TARGET_TIME"

# --- Endpoints ---

@router.post("/calculate")
async def calculate_strategy(
    request: CalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Preview strategy calculation without saving.
    """
    track = db.query(models.Track).filter(models.Track.id == request.track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.file_path or not os.path.exists(track.file_path):
        raise HTTPException(status_code=400, detail="GPX file not available")

    try:
        with open(track.file_path, 'r', encoding='utf-8') as f:
            content = f.read().encode('utf-8')
            
        analytics = GpxAnalytics(content)
        calculator = StrategyCalculator(analytics)
        
        # Convert Pydantic to dicts
        waypoints_data = [w.dict() for w in request.waypoints]
        
        result = calculator.calculate_splits(
            target_time_minutes=request.target_time_minutes,
            waypoints=waypoints_data,
            start_time_hour=request.start_time_hour,
            fatigue_factor=request.fatigue_factor,
            technicity_score=request.technicity_score
        )
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/")
async def save_strategy(
    request: StrategySaveRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Save specific strategy configuration.
    """
    track = db.query(models.Track).filter(models.Track.id == request.track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    new_strategy = models.RaceStrategy(
        user_id=current_user.id,
        track_id=track.id,
        title=request.title,
        target_time_minutes=request.target_time_minutes,
        pacing_method=models.PacingMethod.TARGET_TIME,
        points=[w.dict() for w in request.waypoints],
        global_params={
            "start_time": request.start_time_hour,
            "fatigue_factor": request.fatigue_factor,
            "technicity_score": request.technicity_score
        },
        nutrition_strategy=request.nutrition_strategy
    )
    
    db.add(new_strategy)
    db.commit()
    db.refresh(new_strategy)
    
    return {"id": new_strategy.id, "status": "created"}

@router.get("/track/{track_id}")
async def get_strategies_for_track(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    strategies = db.query(models.RaceStrategy).filter(
        models.RaceStrategy.track_id == track_id,
        models.RaceStrategy.user_id == current_user.id
    ).order_by(models.RaceStrategy.created_at.desc()).all()
    
    return strategies

@router.get("/{strategy_id}")
async def get_strategy_details(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    strategy = db.query(models.RaceStrategy).filter(
        models.RaceStrategy.id == strategy_id, 
        models.RaceStrategy.user_id == current_user.id
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
        

from fastapi.responses import FileResponse
from ..services.image_generator import StrategyImageGenerator

@router.post("/export")
async def export_strategy_image(
    request: CalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Generate and return a PNG roadbook based on the calculation request.
    Does NOT require saving the strategy first.
    """
    track = db.query(models.Track).filter(models.Track.id == request.track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.file_path or not os.path.exists(track.file_path):
        raise HTTPException(status_code=400, detail="GPX file not available")

    try:
        # 1. Calculate Data
        with open(track.file_path, 'r', encoding='utf-8') as f:
            content = f.read().encode('utf-8')
            
        analytics = GpxAnalytics(content)
        calculator = StrategyCalculator(analytics)
        
        waypoints_data = [w.dict() for w in request.waypoints]
        
        result = calculator.calculate_splits(
            target_time_minutes=request.target_time_minutes,
            waypoints=waypoints_data,
            start_time_hour=request.start_time_hour,
            fatigue_factor=request.fatigue_factor,
            technicity_score=request.technicity_score
        )
        
        # 2. Generate Image
        generator = StrategyImageGenerator()
        image_path = generator.generate_roadbook(result, track.title)
        
        return FileResponse(image_path, media_type="image/png", filename=f"roadbook_{track.slug}.png")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

from ..services.pdf_generator import StrategyPdfGenerator

@router.post("/export_pdf")
async def export_strategy_pdf(
    request: CalculationRequest,
    db: Session = Depends(get_db)
):
    """
    Generate and return a PDF roadbook based on the calculation request.
    """
    track = db.query(models.Track).filter(models.Track.id == request.track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.file_path or not os.path.exists(track.file_path):
        raise HTTPException(status_code=400, detail="GPX file not available")

    try:
        # 1. Calculate Data
        with open(track.file_path, 'r', encoding='utf-8') as f:
            content = f.read().encode('utf-8')
            
        analytics = GpxAnalytics(content)
        calculator = StrategyCalculator(analytics)
        
        waypoints_data = [w.dict() for w in request.waypoints]
        
        result = calculator.calculate_splits(
            target_time_minutes=request.target_time_minutes,
            waypoints=waypoints_data,
            start_time_hour=request.start_time_hour,
            fatigue_factor=request.fatigue_factor,
            technicity_score=request.technicity_score
        )
        
        # 2. Generate PDF
        generator = StrategyPdfGenerator()
        
        # Determine username/fullname for header
        user_name = track.user_obj.username if track.user_obj else "Athlète"
        
        pdf_path = generator.generate_pdf(
            track_title=track.title,
            strategy_data=result,
            nutrition=request.nutrition_strategy,
            user_name=user_name
        )
        
        return FileResponse(pdf_path, media_type="application/pdf", filename=f"roadbook_{track.slug}.pdf")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{strategy_id}/pdf")
async def get_strategy_pdf(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Generate PDF from a saved strategy.
    """
    strategy = db.query(models.RaceStrategy).filter(
        models.RaceStrategy.id == strategy_id, 
        models.RaceStrategy.user_id == current_user.id
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    track = strategy.track 
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not track.file_path or not os.path.exists(track.file_path):
        raise HTTPException(status_code=400, detail="GPX file not available")

    try:
        # Re-calculate
        with open(track.file_path, 'r', encoding='utf-8') as f:
            content = f.read().encode('utf-8')
            
        analytics = GpxAnalytics(content)
        calculator = StrategyCalculator(analytics)
        
        # Extract params
        start_time = strategy.global_params.get("start_time", 6.0)
        fatigue = strategy.global_params.get("fatigue_factor", 1.0)
        tech = strategy.global_params.get("technicity_score", 1.0)
        
        result = calculator.calculate_splits(
            target_time_minutes=strategy.target_time_minutes,
            waypoints=strategy.points,
            start_time_hour=start_time,
            fatigue_factor=fatigue,
            technicity_score=tech
        )
        
        # Generate PDF
        generator = StrategyPdfGenerator()
        user_name = current_user.username or "Athlète"
        
        pdf_path = generator.generate_pdf(
            track_title=strategy.title,
            strategy_data=result,
            nutrition=strategy.nutrition_strategy,
            user_name=user_name
        )
        
        return FileResponse(pdf_path, media_type="application/pdf", filename=f"roadbook_{strategy.id}.pdf")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    strategy = db.query(models.RaceStrategy).filter(
        models.RaceStrategy.id == strategy_id, 
        models.RaceStrategy.user_id == current_user.id
    ).first()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    db.delete(strategy)
    db.commit()
    return {"status": "deleted"}
