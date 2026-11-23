#!/usr/bin/env python3
"""One-time interactive helper: run the OAuth consent flow in a browser and
cache the resulting refresh token. Run this once (locally, wherever a
browser is available), not on every refresh.

Usage:
    cd backend && source .venv/bin/activate
    python -m scripts.google_authorize

Requires GOOGLE_CLIENT_SECRETS_FILE (downloaded from Google Cloud Console,
see app/services/google_calendar_client.py for the full setup steps) to
already exist. Writes GOOGLE_TOKEN_FILE on success.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.services.google_calendar_client import SCOPES  # noqa: E402


def main() -> int:
    settings = get_settings()
    secrets_path = Path(settings.google_client_secrets_file)
    if not secrets_path.exists():
        print(f"Client secrets file not found at {secrets_path}.")
        print("Download it from Google Cloud Console (OAuth client, type 'Desktop app')")
        print("and save it at that path, or point GOOGLE_CLIENT_SECRETS_FILE at it.")
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = Path(settings.google_token_file)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())
    token_path.chmod(0o600)

    print(f"Authorized. Token cached at {token_path}")
    print("The daily refresh job will now use this automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
