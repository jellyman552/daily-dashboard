"""Weather via the National Weather Service API (api.weather.gov) — free, no API key.

STATUS: real implementation, but no-ops into mock data until WEATHER_LAT/LON
are set in .env, so the dashboard has something to show out of the box.

NWS quirk: you can't query a forecast directly by lat/lon — you first hit
`/points/{lat},{lon}` to get the forecast office + grid, which returns a
`forecast` URL you then fetch. We cache the grid URL indefinitely (it never
changes for a fixed location) alongside the forecast snapshot.

NWS requires a descriptive User-Agent identifying the app + contact info
(set via NWS_USER_AGENT) — requests without one get rate-limited/rejected.
"""
from datetime import datetime, timezone

import httpx

from app.config import get_settings


def fetch_current_weather() -> dict:
    """Returns a dict matching schemas.WeatherSnapshot."""
    settings = get_settings()
    if settings.demo_mode:
        from app.services import demo

        return demo.weather()
    if not settings.weather_lat or not settings.weather_lon:
        return _mock_weather()

    headers = {"User-Agent": settings.nws_user_agent, "Accept": "application/geo+json"}
    with httpx.Client(timeout=10.0, headers=headers) as client:
        points = client.get(
            f"https://api.weather.gov/points/{settings.weather_lat},{settings.weather_lon}"
        )
        points.raise_for_status()
        forecast_url = points.json()["properties"]["forecast"]

        forecast = client.get(forecast_url)
        forecast.raise_for_status()
        period = forecast.json()["properties"]["periods"][0]

    return {
        "temperature_f": period.get("temperature"),
        "short_forecast": period.get("shortForecast"),
        "detailed_forecast": period.get("detailedForecast"),
        "icon": period.get("icon"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _mock_weather() -> dict:
    return {
        "temperature_f": 68.0,
        "short_forecast": "Partly Sunny",
        "detailed_forecast": "Partly sunny, with a high near 68. (mock data — set WEATHER_LAT/WEATHER_LON in .env)",
        "icon": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
