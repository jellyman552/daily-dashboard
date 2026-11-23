from fastapi import APIRouter, HTTPException

from app.cache.store import read_snapshot
from app.schemas import CalendarSummary

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/today", response_model=CalendarSummary)
def get_todays_events():
    snapshot = read_snapshot("calendar")
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No calendar data yet — run the refresh job first")
    return snapshot
