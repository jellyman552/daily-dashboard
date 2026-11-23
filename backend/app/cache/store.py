"""Tiny file-based cache.

The dashboard is refreshed on a schedule (see `backend/scripts/refresh_data.py`),
not on every request, so "cache" here is just a JSON snapshot per data source
written atomically to disk. Routers read the snapshot; if it's missing (e.g.
before the first refresh has ever run) they return a clear 503 rather than a
stack trace.

Not thread/process-safe for concurrent writers, but the refresh job is a
single cron/timer process, so that's fine here.
"""
import json
import tempfile
from pathlib import Path
from typing import Any

from app.config import get_settings


def _path_for(name: str) -> Path:
    return get_settings().data_dir_path / f"{name}.json"


def write_snapshot(name: str, payload: dict[str, Any]) -> None:
    """Atomically write a JSON snapshot (e.g. name='spending', 'weather', 'calendar', 'recurring')."""
    target = _path_for(name)
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with open(fd, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        Path(tmp_path).replace(target)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def read_snapshot(name: str) -> dict[str, Any] | None:
    path = _path_for(name)
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)
