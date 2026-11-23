import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import calendar, simplefin, spending, transactions, weather
from app.trusted_network import TrustedNetworkMiddleware

# httpx/httpcore log full request URLs at INFO by default — the claimed
# SimpleFIN access URL has Basic Auth credentials embedded in it, so this
# must never be allowed to hit a log line.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

settings = get_settings()

app = FastAPI(title="Daily Dashboard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
if not settings.demo_mode:  # the public demo has no real data to protect
    app.add_middleware(TrustedNetworkMiddleware)

app.include_router(spending.router)
app.include_router(weather.router)
app.include_router(calendar.router)
app.include_router(simplefin.router)
app.include_router(transactions.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "environment": settings.environment, "demo": settings.demo_mode}


@app.on_event("startup")
def _start_scheduler():
    from app import scheduler

    scheduler.start()


# Serve the built frontend (frontend/dist) if it's present, so in production
# one systemd service on one port serves both the UI and the API - simplest
# thing to reach over a single SSH tunnel, and same-origin means no CORS
# fuss. In local dev, `npm run dev` + the Vite proxy is used instead and
# this directory usually won't exist, so mounting is skipped entirely.
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dist, html=True), name="frontend")
