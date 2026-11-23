"""Endpoint that supports linking a SimpleFIN Bridge connection.

Only the claim step happens live, on-demand — spending/recurring data is
still fetched by the daily refresh job and served from cache. The setup
token is single-use and is never logged; neither is the access URL it
produces.
"""
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.schemas import SimpleFinClaimRequest, SimpleFinStatus
from app.services import simplefin_client

router = APIRouter(prefix="/api/simplefin", tags=["simplefin"])


@router.get("/status", response_model=SimpleFinStatus)
def get_status():
    return SimpleFinStatus(linked=simplefin_client.is_linked())


@router.post("/claim", status_code=204)
def claim_setup_token(body: SimpleFinClaimRequest):
    if get_settings().demo_mode:
        raise HTTPException(status_code=403, detail="Linking a bank is turned off in the demo.")
    try:
        simplefin_client.claim_setup_token(body.setup_token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not claim SimpleFIN setup token: {exc}") from exc
