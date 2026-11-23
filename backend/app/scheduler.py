"""Optional in-process daily refresh (REFRESH_AT=HH:MM, local time).

Handy in Docker, where there's no systemd timer: a daemon thread sleeps until
the next REFRESH_AT and runs the refresh (in demo mode, a full demo reset so
visitors' test entries are wiped nightly). Without REFRESH_AT this does
nothing and the external timer in deploy/systemd/ is used instead.
"""
import logging
import threading
import time as _time
from datetime import datetime, timedelta

from app.config import get_settings
from app.localtime import local_now

log = logging.getLogger("scheduler")
_started = False


def _seconds_until(hhmm: str) -> float:
    now = local_now()
    h, m = (int(x) for x in hhmm.split(":"))
    nxt = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(days=1)
    return (nxt - now).total_seconds()


def _run_once() -> None:
    try:
        if get_settings().demo_mode:
            from app.services import demo

            demo.reset()
        else:
            from app.services.refresh import refresh_all

            refresh_all()
        log.info("scheduled refresh done at %s", datetime.now().isoformat(timespec="seconds"))
    except Exception:
        log.exception("scheduled refresh failed")


def _loop(hhmm: str) -> None:
    while True:
        _time.sleep(_seconds_until(hhmm))
        _run_once()


def start() -> None:
    global _started
    hhmm = get_settings().refresh_at.strip()
    if _started or not hhmm:
        return
    _seconds_until(hhmm)  # fail fast on a bad value
    _started = True
    threading.Thread(target=_loop, args=(hhmm,), daemon=True, name="refresh").start()
    log.info("daily refresh scheduled at %s", hhmm)
