"""Manually-entered transactions (typed in, or drafted from a scanned receipt).

These exist to close the gap between "I just bought something" and "my
bank has posted it" - which can be hours to a couple of days. A manual
entry counts toward spending/budgets immediately; once the matching real
bank transaction shows up (same rough amount, within a few days), it's
reconciled away automatically so it isn't counted twice. See
simplefin_client.reconcile_manual_transactions() for that matching logic -
this module only owns the storage.

Stored as a flat JSON list in a gitignored file (backend/data/*). Matched
entries are kept (not deleted) so there's a visible history of what got
reconciled, rather than silently vanishing.
"""
import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.services.categorizer import categorize


def _store_path() -> Path:
    return Path(get_settings().manual_transactions_store)


def _load() -> list[dict]:
    path = _store_path()
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save(rows: list[dict]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)


def add(date: str, amount: float, description: str, category: str | None = None) -> dict:
    """`date` is an ISO date string. `category` is auto-derived from
    `description` (same keyword rules as bank transactions) if not given."""
    row = {
        "id": uuid.uuid4().hex[:12],
        "date": date,
        "amount": round(amount, 2),
        "description": description,
        "category": category or categorize(description),
        "source": "manual",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "matched": False,
        "matched_at": None,
    }
    rows = _load()
    rows.append(row)
    _save(rows)
    return row


def list_all() -> list[dict]:
    return sorted(_load(), key=lambda r: r["date"], reverse=True)


def delete(txn_id: str) -> bool:
    rows = _load()
    remaining = [r for r in rows if r["id"] != txn_id]
    if len(remaining) == len(rows):
        return False
    _save(remaining)
    return True


def unmatched() -> list[dict]:
    return [r for r in _load() if not r["matched"]]


def mark_matched(txn_id: str) -> None:
    rows = _load()
    for row in rows:
        if row["id"] == txn_id:
            row["matched"] = True
            row["matched_at"] = datetime.now(timezone.utc).isoformat()
    _save(rows)


def unmatched_as_spend_dicts(start=None, end=None) -> list[dict]:
    """Unmatched entries in the shape simplefin_client's spending calculators
    expect: {description, amount (negative = spend), posted (date), category}.
    `start`/`end` are dates; `end` is exclusive, matching the rest of the
    codebase's convention."""
    out = []
    for row in unmatched():
        posted = date.fromisoformat(row["date"])
        if start is not None and posted < start:
            continue
        if end is not None and posted >= end:
            continue
        out.append(
            {
                "description": row["description"],
                "amount": -row["amount"],
                "posted": posted,
                "category": row["category"],
            }
        )
    return out
