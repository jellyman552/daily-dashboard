"""The actual refresh logic, importable from both the scheduled CLI script
(scripts/refresh_data.py) and the live app - a manual transaction needs an
immediate recompute of the money snapshots so it counts right away instead
of waiting for the next scheduled run (see routers/transactions.py).
"""
import logging

from app.cache.store import write_snapshot
from app.services import google_calendar_client, simplefin_client, weather_client

log = logging.getLogger("refresh")

# httpx/httpcore log full request URLs at INFO by default — for SimpleFIN that
# URL has Basic Auth credentials embedded in it. Never let those hit a log.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def refresh_money() -> None:
    """Recomputes and caches everything derived from SimpleFIN transactions:
    spending (daily/weekly/monthly), recurring charges, and both budget
    views. Reconciles manual entries against the bank first, so a manual
    entry that's since posted for real doesn't get double-counted.
    """
    simplefin_client.reconcile_manual_transactions()

    summaries = simplefin_client.fetch_spending_summaries()
    for period, payload in summaries.items():
        write_snapshot(f"spending_{period}", payload)

    write_snapshot("recurring", simplefin_client.fetch_recurring_charges())
    write_snapshot("budget", simplefin_client.fetch_monthly_budget())
    write_snapshot("category_budgets", simplefin_client.fetch_category_budgets())


def refresh_all() -> int:
    """Everything: money + weather + calendar. Returns a shell-style exit
    code (0 success, 1 if anything failed) for the CLI script."""
    failures = 0

    try:
        refresh_money()
        log.info("refreshed spending/recurring/budgets")
    except Exception:
        failures += 1
        log.exception("failed to refresh money data")

    for name, fetch in [
        ("weather", weather_client.fetch_current_weather),
        ("calendar", google_calendar_client.fetch_todays_events),
    ]:
        try:
            write_snapshot(name, fetch())
            log.info("refreshed %s", name)
        except Exception:
            failures += 1
            log.exception("failed to refresh %s", name)

    if failures:
        log.error("%d job(s) failed", failures)
    return 1 if failures else 0
