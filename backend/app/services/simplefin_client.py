"""SimpleFIN Bridge integration: real bank/credit-card transactions.

Chosen over Plaid for this personal project because Plaid's production
tier bills per API call (~$0.40/call in one recent quote — a daily refresh
job easily runs $30-70+/month across a couple of accounts). SimpleFIN
Bridge is built for exactly this use case: a flat ~$1.50/mo or $15/yr,
unlimited pulls, no business account required.

One-time setup (do this yourself, not here):
  1. Sign up at a SimpleFIN Bridge provider (e.g. https://beta-bridge.simplefin.org)
     and subscribe to a plan.
  2. Use the bridge's own hosted flow to connect your real bank(s)/card(s) —
     that's SimpleFIN's hosted UI, nothing we need to build here.
  3. The bridge gives you a one-time "setup token" (a long base64 string).
     Paste it into the "Link SimpleFIN" box in the frontend (or POST it
     directly to /api/simplefin/claim) — it's single-use.
  4. This app exchanges it for a permanent access URL (Basic Auth
     credentials embedded in the URL itself) and stores it in the file at
     SIMPLEFIN_ACCESS_URL_STORE (gitignored, chmod 600, never logged).
  5. Connect more accounts later on the bridge and it'll issue a new setup
     token — claim that one too; it replaces the stored access URL.

Caveats vs. Plaid: SimpleFIN gives raw bank transaction descriptions with
no merchant category and no built-in recurring-transaction detection. We do
both ourselves — see categorizer.py and recurring_detector.py.
"""
import base64
import calendar
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.config import get_settings
from app.localtime import local_today
from app.services import manual_transactions
from app.services.categorizer import categorize, is_income
from app.services.recurring_detector import detect_recurring

log = logging.getLogger(__name__)


def _access_url_path() -> Path:
    return Path(get_settings().simplefin_access_url_store)


def _load_access_url() -> str | None:
    path = _access_url_path()
    if not path.exists():
        return None
    return path.read_text().strip() or None


def _save_access_url(access_url: str) -> None:
    path = _access_url_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(access_url)
    path.chmod(0o600)


def is_linked() -> bool:
    if get_settings().demo_mode:
        return True
    return _load_access_url() is not None


def claim_setup_token(setup_token: str) -> None:
    """Exchanges a one-time SimpleFIN setup token for a permanent access URL.
    Never logs the token or the resulting URL — it carries embedded credentials."""
    claim_url = base64.b64decode(setup_token).decode("utf-8")
    with httpx.Client(timeout=15.0) as client:
        response = client.post(claim_url)
        response.raise_for_status()
        access_url = response.text.strip()
    _save_access_url(access_url)
    log.info("claimed a new SimpleFIN access URL")


def _fetch_account_set(start: date, end: date) -> dict:
    if get_settings().demo_mode:
        from app.services import demo

        return demo.account_set(start, end)
    access_url = _load_access_url()
    if access_url is None:
        raise RuntimeError("No SimpleFIN account linked yet — POST a setup token to /api/simplefin/claim")

    params = {
        "start-date": int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
        "end-date": int(datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc).timestamp()),
        # Include pending transactions, not just posted ones - a purchase made
        # an hour ago is more useful to see now than to wait 1-2 days for it
        # to post. Safe against double-counting: we recompute fresh from the
        # live account state on every refresh rather than accumulating
        # history, so once a pending charge posts (and replaces the pending
        # entry, per the SimpleFIN protocol), the next refresh just reflects
        # that - there's no separate stored "pending" record left behind.
        "pending": 1,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{access_url}/accounts", params=params)
        response.raise_for_status()
        return response.json()


def _extract_transactions(account_set: dict) -> list[dict]:
    """Flattens every account's transactions into
    {description, amount (signed - positive=deposit, negative=spend), posted (date)}."""
    out = []
    for account in account_set.get("accounts", []):
        for txn in account.get("transactions", []):
            out.append(
                {
                    "description": txn.get("description", ""),
                    "amount": float(txn["amount"]),
                    "posted": datetime.fromtimestamp(int(txn["posted"]), tz=timezone.utc).date(),
                }
            )
    return out


def _with_manual(transactions: list[dict], start: date, end: date) -> list[dict]:
    """Adds unmatched manual entries (typed in, or from a scanned receipt)
    in the given [start, end) window to a list of real bank transactions,
    so a purchase you just logged counts immediately rather than waiting
    for the bank to post it. See reconcile_manual_transactions() for how a
    manual entry gets removed from this list once the bank catches up."""
    return transactions + manual_transactions.unmatched_as_spend_dicts(start, end)


# How many days apart a manual entry and a real bank transaction can be and
# still count as "the same purchase" - banks/SimpleFIN can take a day or two
# to post something you bought today.
_RECONCILE_DATE_WINDOW_DAYS = 3
_RECONCILE_AMOUNT_TOLERANCE = 0.01


def reconcile_manual_transactions() -> int:
    """Checks unmatched manual entries against recent real bank transactions;
    marks a manual entry matched once the real one shows up, so it stops
    being counted (the real transaction takes over). Only auto-matches when
    exactly one manual entry is a plausible match for a given bank
    transaction - an ambiguous case (e.g. two $12 lunches the same week) is
    left alone rather than risk matching the wrong one.

    Called once per refresh (see app/services/refresh.py), not on every
    spending calculation - matching is a mutation, not a read.
    """
    pending = manual_transactions.unmatched()
    if not is_linked() or not pending:
        return 0

    today = local_today()
    lookback = today - timedelta(days=_RECONCILE_DATE_WINDOW_DAYS + 1)
    account_set = _fetch_account_set(lookback, today + timedelta(days=1))
    bank_spends = [t for t in _extract_transactions(account_set) if t["amount"] < 0]

    matched_count = 0
    for entry in pending:
        entry_date = date.fromisoformat(entry["date"])
        candidates = [
            b
            for b in bank_spends
            if abs(-b["amount"] - entry["amount"]) < _RECONCILE_AMOUNT_TOLERANCE
            and abs((b["posted"] - entry_date).days) <= _RECONCILE_DATE_WINDOW_DAYS
        ]
        if len(candidates) == 1:
            manual_transactions.mark_matched(entry["id"])
            matched_count += 1
    return matched_count


def _summarize_spending(transactions: list[dict], period: str, start: date, end: date) -> dict:
    """`end` is exclusive. Transfers (see categorizer.is_transfer) are excluded -
    they're not real expenses.

    A deposit that happens to match a real spend category (e.g. a partner's
    Zelle memo'd "Rent" landing in Housing via the existing "rent" keyword)
    nets against that category instead of being invisible - otherwise a
    jointly-paid bill looks like it costs you the full amount every month.
    Deposits that don't match any category (payroll, one-off Zelles, etc.)
    are still ignored here, same as before.
    """
    totals: dict[str, float] = {}
    grand_total = 0.0
    for txn in transactions:
        if not (start <= txn["posted"] < end):
            continue
        # Manual entries already carry a resolved category (auto-derived or
        # user-picked at entry time) - use that instead of re-deriving it.
        category = txn.get("category") or categorize(txn["description"])
        if category == "Transfer":
            continue
        if txn["amount"] < 0:
            spend = -txn["amount"]
            totals[category] = totals.get(category, 0.0) + spend
            grand_total += spend
        elif txn["amount"] > 0 and category != "Other":
            totals[category] = totals.get(category, 0.0) - txn["amount"]
            grand_total -= txn["amount"]

    by_category = [
        {"category": k, "amount": round(v, 2)} for k, v in sorted(totals.items(), key=lambda kv: -kv[1])
    ]
    return {
        "period": period,
        "period_start": start.isoformat(),
        "period_end": (end - timedelta(days=1)).isoformat(),
        "total": round(grand_total, 2),
        "by_category": by_category,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_spending_summaries() -> dict:
    """Returns {"daily": ..., "weekly": ..., "monthly": ...}, each a dict
    matching schemas.SpendingSummary - computed from a single account fetch."""
    if not is_linked():
        return _mock_spending_summaries()

    today = local_today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    fetch_start = min(week_start, month_start)  # covers all three periods in one call

    account_set = _fetch_account_set(fetch_start, today + timedelta(days=1))
    transactions = _with_manual(_extract_transactions(account_set), fetch_start, today + timedelta(days=1))

    return {
        "daily": _summarize_spending(transactions, "daily", today, today + timedelta(days=1)),
        "weekly": _summarize_spending(transactions, "weekly", week_start, week_start + timedelta(days=7)),
        "monthly": _summarize_spending(transactions, "monthly", month_start, today + timedelta(days=1)),
    }


def fetch_monthly_budget() -> dict:
    """This month's income (paycheck deposits, see categorizer.is_income) vs.
    spending so far. Returns a dict matching schemas.MonthlyBudget."""
    if not is_linked():
        return _mock_monthly_budget()

    today = local_today()
    month_start = today.replace(day=1)
    account_set = _fetch_account_set(month_start, today + timedelta(days=1))
    transactions = _with_manual(_extract_transactions(account_set), month_start, today + timedelta(days=1))

    income = sum(
        t["amount"] for t in transactions if t["amount"] > 0 and is_income(t["description"])
    )
    # Reuse the same netting logic as the spending tabs, so this always
    # matches what "This Month" shows - no separate, slightly-different number.
    spent = _summarize_spending(transactions, "monthly", month_start, today + timedelta(days=1))["total"]

    return {
        "month_start": month_start.isoformat(),
        "month_end": today.isoformat(),
        "income": round(income, 2),
        "spent": round(spent, 2),
        "remaining": round(income - spent, 2),
        "percent_used": round(spent / income * 100, 1) if income > 0 else None,
        "status": "over" if spent > income else "under",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_budgets() -> dict[str, float]:
    """backend/data/budgets.json: {"Groceries": 400, ...} - gitignored since
    these are personal dollar amounts, same treatment as custom_categories.json."""
    path = Path(get_settings().data_dir) / "budgets.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def fetch_category_budgets() -> dict:
    """Per-category budget caps vs. spending so far this month - the "can I
    afford to eat out" check. Returns a dict matching schemas.CategoryBudgetsSummary."""
    budgets = _load_budgets()
    if not is_linked() or not budgets:
        return _mock_category_budgets()

    today = local_today()
    month_start = today.replace(day=1)
    account_set = _fetch_account_set(month_start, today + timedelta(days=1))
    transactions = _with_manual(_extract_transactions(account_set), month_start, today + timedelta(days=1))

    monthly = _summarize_spending(transactions, "monthly", month_start, today + timedelta(days=1))
    spent_by_category = {c["category"]: c["amount"] for c in monthly["by_category"]}

    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_remaining = days_in_month - today.day + 1  # counts today

    categories = []
    for category, budget in budgets.items():
        spent = spent_by_category.get(category, 0.0)
        remaining = budget - spent
        percent_used = round(spent / budget * 100, 1) if budget > 0 else 0.0
        status = "over" if percent_used >= 100 else "near" if percent_used >= 80 else "under"
        categories.append(
            {
                "category": category,
                "budget": budget,
                "spent": round(spent, 2),
                "remaining": round(remaining, 2),
                "percent_used": percent_used,
                "status": status,
                "safe_per_day": round(remaining / days_remaining, 2) if remaining > 0 else None,
            }
        )

    categories.sort(key=lambda c: -c["percent_used"])  # most at-risk first
    return {
        "month_start": month_start.isoformat(),
        "month_end": today.isoformat(),
        "categories": categories,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_recurring_charges() -> dict:
    """Returns a dict matching schemas.RecurringSummary."""
    if not is_linked():
        return _mock_recurring()

    today = local_today()
    lookback_start = today - timedelta(days=120)  # need history to detect a pattern
    account_set = _fetch_account_set(lookback_start, today + timedelta(days=1))
    transactions = _with_manual(_extract_transactions(account_set), lookback_start, today + timedelta(days=1))

    spends = [
        {"description": t["description"], "amount": -t["amount"], "posted": t["posted"]}
        for t in transactions
        if t["amount"] < 0
    ]

    charges = detect_recurring(spends, today=today)
    return {"charges": charges, "updated_at": datetime.now(timezone.utc).isoformat()}


def _mock_spending_summaries() -> dict:
    today = local_today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    now = datetime.now(timezone.utc).isoformat()
    return {
        "daily": {
            "period": "daily",
            "period_start": today.isoformat(),
            "period_end": today.isoformat(),
            "total": 42.18,
            "by_category": [
                {"category": "Restaurants", "amount": 28.50},
                {"category": "Transportation", "amount": 13.68},
            ],
            "updated_at": now,
        },
        "weekly": {
            "period": "weekly",
            "period_start": week_start.isoformat(),
            "period_end": (week_start + timedelta(days=6)).isoformat(),
            "total": 312.47,
            "by_category": [
                {"category": "Groceries", "amount": 98.21},
                {"category": "Restaurants", "amount": 64.30},
                {"category": "Transportation", "amount": 45.00},
                {"category": "Entertainment", "amount": 29.96},
                {"category": "Shopping", "amount": 75.00},
            ],
            "updated_at": now,
        },
        "monthly": {
            "period": "monthly",
            "period_start": month_start.isoformat(),
            "period_end": today.isoformat(),
            "total": 1284.55,
            "by_category": [
                {"category": "Groceries", "amount": 412.20},
                {"category": "Restaurants", "amount": 298.40},
                {"category": "Housing", "amount": 350.00},
                {"category": "Transportation", "amount": 120.00},
                {"category": "Entertainment", "amount": 103.95},
            ],
            "updated_at": now,
        },
    }


def _mock_monthly_budget() -> dict:
    today = local_today()
    month_start = today.replace(day=1)
    income, spent = 3600.00, 1284.55
    return {
        "month_start": month_start.isoformat(),
        "month_end": today.isoformat(),
        "income": income,
        "spent": spent,
        "remaining": round(income - spent, 2),
        "percent_used": round(spent / income * 100, 1),
        "status": "over" if spent > income else "under",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _mock_category_budgets() -> dict:
    today = local_today()
    month_start = today.replace(day=1)
    rows = [
        ("Restaurants", 250, 210),
        ("Groceries", 400, 260),
        ("Shopping", 110, 40),
        ("Household", 25, 0),
    ]
    days_remaining = calendar.monthrange(today.year, today.month)[1] - today.day + 1
    categories = []
    for category, budget, spent in rows:
        remaining = budget - spent
        percent_used = round(spent / budget * 100, 1)
        categories.append(
            {
                "category": category,
                "budget": budget,
                "spent": spent,
                "remaining": remaining,
                "percent_used": percent_used,
                "status": "over" if percent_used >= 100 else "near" if percent_used >= 80 else "under",
                "safe_per_day": round(remaining / days_remaining, 2) if remaining > 0 else None,
            }
        )
    return {
        "month_start": month_start.isoformat(),
        "month_end": today.isoformat(),
        "categories": categories,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _mock_recurring() -> dict:
    return {
        "charges": [
            {"merchant": "Netflix", "amount": 15.49, "frequency": "MONTHLY", "last_date": "2026-08-15", "is_active": True, "kind": "subscription"},
            {"merchant": "Spotify", "amount": 11.99, "frequency": "MONTHLY", "last_date": "2026-08-20", "is_active": True, "kind": "subscription"},
            {"merchant": "Amazon Prime", "amount": 139.00, "frequency": "ANNUALLY", "last_date": "2026-03-02", "is_active": True, "kind": "subscription"},
            {"merchant": "Car Insurance", "amount": 112.40, "frequency": "MONTHLY", "last_date": "2026-08-28", "is_active": True, "kind": "bill"},
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
