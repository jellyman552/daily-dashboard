from fastapi import APIRouter, HTTPException

from app.cache.store import read_snapshot
from app.schemas import CategoryBudgetsSummary, MonthlyBudget, RecurringSummary, SpendingSummary
from app.services.categorizer import known_categories

router = APIRouter(prefix="/api/spending", tags=["spending"])


@router.get("/categories", response_model=list[str])
def get_known_categories():
    """For populating a category picker in the manual-entry form."""
    return known_categories()


def _get_period(name: str) -> SpendingSummary:
    snapshot = read_snapshot(f"spending_{name}")
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No spending data yet — run the refresh job first")
    return snapshot


@router.get("/daily", response_model=SpendingSummary)
def get_daily_spending():
    return _get_period("daily")


@router.get("/weekly", response_model=SpendingSummary)
def get_weekly_spending():
    return _get_period("weekly")


@router.get("/monthly", response_model=SpendingSummary)
def get_monthly_spending():
    return _get_period("monthly")


@router.get("/budget", response_model=MonthlyBudget)
def get_monthly_budget():
    snapshot = read_snapshot("budget")
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No budget data yet — run the refresh job first")
    return snapshot


@router.get("/budgets", response_model=CategoryBudgetsSummary)
def get_category_budgets():
    snapshot = read_snapshot("category_budgets")
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No category budget data yet — run the refresh job first")
    return snapshot


@router.get("/recurring", response_model=RecurringSummary)
def get_recurring_charges():
    snapshot = read_snapshot("recurring")
    if snapshot is None:
        raise HTTPException(status_code=503, detail="No recurring-charge data yet — run the refresh job first")
    return snapshot
