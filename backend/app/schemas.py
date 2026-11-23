"""Pydantic response models shared by the routers and the refresh script.

Keeping these separate from the fetch/refresh logic means the frontend's
contract is defined in one obvious place.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CategorySpend(BaseModel):
    category: str
    amount: float


class SpendingSummary(BaseModel):
    period: str  # "daily" | "weekly" | "monthly"
    period_start: str  # ISO date
    period_end: str  # ISO date
    total: float
    by_category: list[CategorySpend]
    updated_at: datetime


class MonthlyBudget(BaseModel):
    month_start: str  # ISO date
    month_end: str  # ISO date (today, i.e. month-to-date)
    income: float  # paycheck deposits this month
    spent: float  # real spending this month (transfers excluded)
    remaining: float  # income - spent
    percent_used: float | None  # spent / income * 100, None if no income detected
    status: str  # "under" | "over" -> frontend maps to green/red
    updated_at: datetime


class CategoryBudget(BaseModel):
    category: str
    budget: float
    spent: float  # this month, net of reimbursements - same logic as SpendingSummary
    remaining: float  # budget - spent
    percent_used: float
    status: str  # "under" | "near" | "over"
    safe_per_day: float | None  # remaining / days left in month, None once over budget


class CategoryBudgetsSummary(BaseModel):
    month_start: str  # ISO date
    month_end: str  # ISO date (today, i.e. month-to-date)
    categories: list[CategoryBudget]
    updated_at: datetime


class RecurringCharge(BaseModel):
    merchant: str
    amount: float
    frequency: str  # e.g. "MONTHLY", "WEEKLY", "ANNUALLY"
    last_date: str  # ISO date
    is_active: bool
    kind: str  # "subscription" | "bill" | "other"


class RecurringSummary(BaseModel):
    charges: list[RecurringCharge]
    updated_at: datetime


class WeatherSnapshot(BaseModel):
    temperature_f: float | None = None
    short_forecast: str | None = None
    detailed_forecast: str | None = None
    icon: str | None = None
    updated_at: datetime


class CalendarEvent(BaseModel):
    title: str
    start: str  # ISO datetime, or ISO date for all-day events
    end: str
    all_day: bool = False
    location: str | None = None


class CalendarSummary(BaseModel):
    events: list[CalendarEvent]
    updated_at: datetime


class SimpleFinClaimRequest(BaseModel):
    setup_token: str


class SimpleFinStatus(BaseModel):
    linked: bool


class ManualTransactionCreate(BaseModel):
    date: str  # ISO date
    amount: float
    description: str
    category: str | None = None  # auto-derived from description if omitted


class ManualTransaction(BaseModel):
    id: str
    date: str
    amount: float
    description: str
    category: str
    source: str  # "manual" | "receipt"
    created_at: datetime
    matched: bool
    matched_at: datetime | None


class ReceiptParseResult(BaseModel):
    date: str
    amount: float
    merchant: str
