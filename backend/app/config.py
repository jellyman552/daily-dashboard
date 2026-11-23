"""Centralized, env-driven settings.

Nothing sensitive is hardcoded here — everything comes from the environment
(populated locally via `.env`, and via systemd `EnvironmentFile=` in
production). See `backend/.env.example` for the full list of variables.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    cors_origins: str = "http://localhost:5173"
    data_dir: str = "./data"
    # IANA timezone name, e.g. "America/Los_Angeles". Used anywhere "today"
    # needs to mean *your* today, not the server's - the Oracle instance runs
    # on UTC, so without this, evening events/spending get attributed to the
    # wrong calendar day.
    timezone: str = "America/Los_Angeles"

    # Public demo: fictional bank/weather/calendar data, no account linking,
    # open to any network. See app/services/demo.py.
    demo_mode: bool = False
    # Daily refresh inside the app (HH:MM, local time), e.g. "05:00" in Docker.
    # Empty = rely on an external scheduler (the systemd timer in deploy/).
    refresh_at: str = ""
    # Extra CIDRs allowed past the trusted-network check, comma-separated -
    # e.g. Docker's bridge range when the port is published to 127.0.0.1 only.
    extra_trusted_networks: str = ""

    # SimpleFIN Bridge
    simplefin_access_url_store: str = "./data/simplefin_access_url.txt"

    # Manual transaction entry + receipt scanning (Tesseract OCR, local & free)
    manual_transactions_store: str = "./data/manual_transactions.json"

    # Weather
    weather_lat: str = ""
    weather_lon: str = ""
    nws_user_agent: str = "daily-dashboard (set NWS_USER_AGENT in .env)"

    # Google Calendar
    google_client_secrets_file: str = "./data/google_client_secret.json"
    google_token_file: str = "./data/google_token.json"
    google_calendar_id: str = "primary"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def data_dir_path(self) -> Path:
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
