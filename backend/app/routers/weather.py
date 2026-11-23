from fastapi import APIRouter, HTTPException

from app.cache.store import read_snapshot
from app.schemas import WeatherSnapshot

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("", response_model=WeatherSnapshot)
def get_weather():
    snapshot = read_snapshot("weather")
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No weather data yet — run the refresh job first")
    return snapshot
