"""Google Calendar integration: today's events.

One-time setup (do this yourself, not here):
  1. In Google Cloud Console, create a project (or reuse one) and enable
     the "Google Calendar API".
  2. Configure the OAuth consent screen as "External" + "Testing" (fine for
     personal use — just add your own Google account as a test user), or
     "Internal" if you're on Google Workspace.
  3. Create an OAuth client ID of type "Desktop app". Download the JSON and
     save it as the path in GOOGLE_CLIENT_SECRETS_FILE (default
     backend/data/google_client_secret.json — gitignored, never commit it).
  4. Run the one-time authorization helper, which opens a browser:
         cd backend && source .venv/bin/activate
         python -m scripts.google_authorize
     This writes a refresh token to GOOGLE_TOKEN_FILE (default
     backend/data/google_token.json — also gitignored). After that, the
     daily refresh job renews the access token silently — no browser needed
     again unless you revoke access.

If deploying to a headless server: run the authorize step locally (step 4,
here, where a browser exists), then copy the resulting google_token.json
over to the server's backend/data/ (e.g. `scp`) — never through git.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings
from app.localtime import local_now

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def _load_credentials() -> Credentials:
    settings = get_settings()
    token_path = Path(settings.google_token_file)
    if not token_path.exists():
        raise RuntimeError(
            "No Google token file found. Run `python -m scripts.google_authorize` once "
            "(see app/services/google_calendar_client.py for setup steps)."
        )

    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
    return creds


def fetch_todays_events() -> dict:
    """Returns a dict matching schemas.CalendarSummary."""
    if get_settings().demo_mode:
        from app.services import demo

        return demo.calendar()
    settings = get_settings()
    if not Path(settings.google_token_file).exists():
        return _mock_calendar()

    creds = _load_credentials()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    now = local_now()  # *your* timezone, not the server's (see app/localtime.py)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    response = (
        service.events()
        .list(
            calendarId=settings.google_calendar_id,
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in response.get("items", []):
        start = item["start"]
        end = item["end"]
        all_day = "date" in start  # all-day events use "date" instead of "dateTime"
        events.append(
            {
                "title": item.get("summary", "(no title)"),
                "start": start.get("dateTime", start.get("date")),
                "end": end.get("dateTime", end.get("date")),
                "all_day": all_day,
                "location": item.get("location"),
            }
        )

    return {"events": events, "updated_at": datetime.now(timezone.utc).isoformat()}


def _mock_calendar() -> dict:
    now = datetime.now(timezone.utc)
    today_9am = now.replace(hour=16, minute=0, second=0, microsecond=0)  # ~9am PT in UTC
    return {
        "events": [
            {
                "title": "Team standup",
                "start": today_9am.isoformat(),
                "end": (today_9am + timedelta(minutes=15)).isoformat(),
                "all_day": False,
                "location": None,
            },
            {
                "title": "1:1 with manager",
                "start": (today_9am + timedelta(hours=2)).isoformat(),
                "end": (today_9am + timedelta(hours=2, minutes=30)).isoformat(),
                "all_day": False,
                "location": "Zoom",
            },
        ],
        "updated_at": now.isoformat(),
    }
