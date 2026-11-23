""""Today" for a human always means their own calendar day, not the
server's. The Oracle instance runs on UTC, so anywhere "today" / "this
week" / "this month" gets computed from the server's own clock, it's
actually the *wrong* day for several hours around evening Pacific time
(UTC rolls to the next date at 5pm Pacific / 4pm during PDT).

Found via a real bug: two evening calendar events were invisible because
the day-boundary query was built in UTC. The same bug shape existed in
every spending/budget date boundary too - all fixed to use this instead.

`updated_at` timestamps are a different concern (just "when was this
computed") and are correctly left as UTC elsewhere - only day-boundary
math ("today", "this week", "this month") needs to go through here.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def local_now() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone))


def local_today() -> date:
    return local_now().date()
