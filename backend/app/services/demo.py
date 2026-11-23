"""Demo mode (DEMO_MODE=true): fictional data for the public demo.

Instead of hand-written totals, this stands in for the bank: `account_set()`
returns about five months of made-up transactions in the same shape SimpleFIN
returns, and the real pipeline (categorizer, recurring-charge detector,
budgets, manual-entry reconciliation) runs on top of it. Weather and calendar
get plausible snapshots for "today".

Everything is deterministic per date, so a refresh during the day shows the
same numbers, and `reset()` (run at startup and nightly) rebuilds a clean demo.
"""
import json
import random
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.localtime import local_today

HISTORY_DAYS = 150

DEMO_BUDGETS = {"Groceries": 600, "Restaurants": 360, "Transportation": 160, "Shopping": 250, "Entertainment": 60}

# (day of month, description, amount or (low, high))
MONTHLY = [
    (1, "PARKSIDE APARTMENTS RENT", 1650.00),
    (3, "LEMONADE RENTERS INS", 14.25),
    (5, "GEICO AUTO INSURANCE", 112.40),
    (7, "PLANET FITNESS MEMBERSHIP", 24.99),
    (9, "NETFLIX.COM", 15.49),
    (12, "PG&E WEB ONLINE", (58.0, 104.0)),
    (14, "SPOTIFY USA", 11.99),
    (16, "ONLINE TRANSFER TO SAVINGS", 300.00),
    (18, "COMCAST XFINITY", 69.99),
    (20, "APPLE.COM/BILL ICLOUD", 2.99),
    (22, "VERIZON WIRELESS", 55.00),
    (26, "GITHUB INC", 4.00),
]
PAYDAY_ANCHOR = date(2026, 1, 2)  # a Friday; paid every other Friday from here
GROCERS = ["TRADER JOE'S #212", "SAFEWAY #1835", "COSTCO WHSE #0465", "SPROUTS FARMERS MKT"]
FOOD = [("STARBUCKS STORE 5521", 4.5, 8.5), ("CHIPOTLE 1204", 10.5, 15.0), ("DOORDASH*THAI BASIL", 21.0, 38.0),
        ("PANERA BREAD #601", 9.0, 16.0), ("TACO BELL #3381", 6.0, 12.0), ("IN-N-OUT BURGER #120", 8.0, 14.0)]
SHOPS = [("AMAZON MKTPL*2K4", 9.0, 78.0), ("TARGET 00027", 14.0, 65.0), ("BEST BUY 00112", 19.0, 120.0)]


def _rng(day: date, label: str) -> random.Random:
    return random.Random(f"{day.isoformat()}|{label}")


def _amount(day: date, label: str, spec) -> float:
    if isinstance(spec, tuple):
        return round(_rng(day, label).uniform(*spec), 2)
    return spec


def _transactions_on(day: date) -> list[tuple[str, float]]:
    """(description, signed amount) for one day: negative = spend."""
    out: list[tuple[str, float]] = []
    if (day - PAYDAY_ANCHOR).days % 14 == 0:
        out.append(("ACME CORP PAYROLL DIRECT DEP", 2140.00))
    for dom, desc, spec in MONTHLY:
        if day.day == dom:
            out.append((desc, -_amount(day, desc, spec)))
    if day.weekday() in (2, 6):  # Wednesday and Sunday groceries
        r = _rng(day, "grocer")
        out.append((r.choice(GROCERS), -round(r.uniform(32, 128), 2)))
    r = _rng(day, "food")
    for _ in range(r.choice([0, 1, 1, 2])):
        desc, lo, hi = r.choice(FOOD)
        out.append((desc, -round(r.uniform(lo, hi), 2)))
    if day.toordinal() % 9 == 0:
        out.append(("CHEVRON 0091842", -round(_rng(day, "gas").uniform(41, 58), 2)))
    r = _rng(day, "shop")
    if r.random() < 0.16:
        desc, lo, hi = r.choice(SHOPS)
        out.append((desc, -round(r.uniform(lo, hi), 2)))
    if day.toordinal() % 23 == 0:
        out.append(("AMC THEATRES 1204", -round(_rng(day, "amc").uniform(14, 32), 2)))
    return out


def account_set(start: date, end: date) -> dict:
    """SimpleFIN-shaped {"accounts": [...]} for [start, end), capped at today."""
    today = local_today()
    first = max(start, today - timedelta(days=HISTORY_DAYS))
    last = min(end, today + timedelta(days=1))
    txns = []
    day = first
    while day < last:
        posted = int(datetime.combine(day, time(12), tzinfo=timezone.utc).timestamp())
        for i, (desc, amount) in enumerate(_transactions_on(day)):
            txns.append({"id": f"demo-{day.isoformat()}-{i}", "description": desc,
                         "amount": f"{amount:.2f}", "posted": posted})
        day += timedelta(days=1)
    return {"errors": [], "accounts": [{"id": "demo-checking", "name": "Demo Checking", "transactions": txns}]}


def weather() -> dict:
    return {
        "temperature_f": 66.0,
        "short_forecast": "Mostly Sunny",
        "detailed_forecast": "Mostly sunny, with a high near 66. West wind 5 to 10 mph.",
        "icon": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def calendar() -> dict:
    tz = ZoneInfo(get_settings().timezone)
    today = local_today()

    def at(h, m, minutes, title, location=None):
        start = datetime.combine(today, time(h, m), tzinfo=tz)
        return {"title": title, "start": start.isoformat(), "end": (start + timedelta(minutes=minutes)).isoformat(),
                "all_day": False, "location": location}

    return {
        "events": [
            at(9, 30, 15, "Team standup", "Zoom"),
            at(12, 0, 60, "Lunch with Sam", "Corner Café"),
            at(16, 15, 45, "Dentist"),
            at(19, 0, 90, "Climbing gym"),
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def reset() -> int:
    """Wipe the data dir (snapshots and visitors' manual entries), write demo
    budgets, then run the normal refresh against the demo bank."""
    from app.services.refresh import refresh_all

    data = get_settings().data_dir_path
    for f in data.glob("*.json"):
        f.unlink()
    (data / "budgets.json").write_text(json.dumps(DEMO_BUDGETS, indent=2))
    return refresh_all()
