#!/usr/bin/env python3
"""Cron/systemd-timer entry point: pull fresh data from each source and
write it to the local cache. The FastAPI app never calls these APIs
directly on a page load — it only ever reads what this last wrote (except
for a manual transaction, which triggers the same refresh immediately -
see app/services/refresh.py, the actual logic lives there so both this
script and the live app can call it).

Run manually:
    cd backend && source .venv/bin/activate && python -m scripts.refresh_data

Scheduled (see deploy/systemd/daily-dashboard-refresh.timer for the
production schedule).
"""
import logging
import sys
from pathlib import Path

# Allow running as `python scripts/refresh_data.py` without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.refresh import refresh_all  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    raise SystemExit(refresh_all())
