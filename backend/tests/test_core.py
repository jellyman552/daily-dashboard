"""Core money logic, run against the fictional demo bank."""
import json
from datetime import date

import pytest

from app.config import get_settings


@pytest.fixture
def demo(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    from app.services import demo as demo_mod

    assert demo_mod.reset() == 0
    yield tmp_path
    get_settings.cache_clear()


def test_categorizer_word_boundary():
    from app.services.categorizer import categorize

    assert categorize("CHIPOTLE 1204") == "Restaurants"
    assert categorize("CONF CODE AB120DMV") == "Other"  # 'dmv' inside a code isn't the DMV
    assert categorize("ONLINE TRANSFER TO SAVINGS") == "Transfer"


def test_demo_pipeline_builds_every_snapshot(demo):
    for name in ["spending_daily", "spending_weekly", "spending_monthly", "budget",
                 "category_budgets", "recurring", "weather", "calendar"]:
        assert (demo / f"{name}.json").exists(), name


def test_transfers_are_not_spending(demo):
    monthly = json.loads((demo / "spending_monthly.json").read_text())
    assert "Transfer" not in {c["category"] for c in monthly["by_category"]}


def test_recurring_detector_finds_subscriptions_and_bills(demo):
    charges = json.loads((demo / "recurring.json").read_text())["charges"]
    kinds = {c["merchant"]: c["kind"] for c in charges}
    assert kinds.get("Spotify Usa") == "subscription"
    assert kinds.get("Parkside Apartments Rent") == "bill"
    assert all(c["frequency"] == "MONTHLY" for c in charges)


def test_manual_entry_reconciles_with_matching_bank_charge(demo):
    from app.services import manual_transactions, simplefin_client
    from app.services.demo import account_set

    today = date.today()
    bank = [t for t in account_set(today.replace(day=1), today)["accounts"][0]["transactions"]
            if float(t["amount"]) < 0][-1]
    row = manual_transactions.add(today.isoformat(), -float(bank["amount"]), bank["description"])
    simplefin_client.reconcile_manual_transactions()
    assert any(r["id"] == row["id"] and r["matched"] for r in manual_transactions.list_all())


def test_seed_refuses_without_demo_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    import subprocess, sys
    r = subprocess.run([sys.executable, "-m", "scripts.seed_demo"], capture_output=True, text=True)
    assert r.returncode != 0 and "DEMO_MODE" in (r.stdout + r.stderr)
