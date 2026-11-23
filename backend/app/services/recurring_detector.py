"""Homegrown recurring-charge detector.

SimpleFIN has no equivalent of Plaid's Recurring Transactions endpoint, so
we infer subscriptions ourselves: group transactions by a normalized
merchant key, then flag groups that repeat at a roughly consistent amount
and interval. Simple on purpose — tune the tolerances below if it's too
loose or too strict for your own accounts.
"""
import re
from collections import defaultdict
from datetime import date
from statistics import mean, pstdev

from app.services.categorizer import classify_recurring_kind, is_transfer

# (label, min days, max days) matched against the average gap between
# consecutive charges from the same merchant.
_FREQUENCY_BANDS = [
    ("WEEKLY", 5, 9),
    ("BIWEEKLY", 12, 16),
    ("MONTHLY", 25, 35),
    ("QUARTERLY", 80, 100),
    ("ANNUALLY", 350, 380),
]

_AMOUNT_TOLERANCE = 0.10  # relative tolerance between charges to count as "the same" amount
_GAP_TOLERANCE = 0.35  # relative stdev tolerance on the interval between charges


def _merchant_key(description: str) -> str:
    text = re.sub(r"[^A-Za-z ]", " ", description).upper()
    words = [w for w in text.split() if len(w) > 1]
    return " ".join(words[:3])  # the first couple of meaningful words is usually the merchant name


def detect_recurring(transactions: list[dict], today: date | None = None) -> list[dict]:
    """`transactions`: list of {description, amount (positive = a spend), posted (date)}.
    Returns a list of dicts matching schemas.RecurringCharge.
    """
    today = today or date.today()

    groups: dict[str, list[dict]] = defaultdict(list)
    for txn in transactions:
        if is_transfer(txn["description"]):
            continue  # a savings contribution or self-payment, not a recurring bill/subscription
        key = _merchant_key(txn["description"])
        if key:
            groups[key].append(txn)

    charges = []
    for key, txns in groups.items():
        if len(txns) < 2:
            continue
        txns.sort(key=lambda t: t["posted"])

        amounts = [t["amount"] for t in txns]
        avg_amount = mean(amounts)
        if avg_amount <= 0:
            continue
        if any(abs(a - avg_amount) / avg_amount > _AMOUNT_TOLERANCE for a in amounts):
            continue  # amounts too inconsistent to be a fixed subscription

        gaps = [(txns[i]["posted"] - txns[i - 1]["posted"]).days for i in range(1, len(txns))]
        avg_gap = mean(gaps)
        if avg_gap <= 0:
            continue
        if len(gaps) > 1 and pstdev(gaps) > avg_gap * _GAP_TOLERANCE:
            continue  # too irregular to call it recurring

        frequency = next((label for label, lo, hi in _FREQUENCY_BANDS if lo <= avg_gap <= hi), None)
        if frequency is None:
            continue

        last = txns[-1]
        is_active = (today - last["posted"]).days <= avg_gap * 1.5

        charges.append(
            {
                "merchant": key.title(),
                "amount": round(avg_amount, 2),
                "frequency": frequency,
                "last_date": last["posted"].isoformat(),
                "is_active": is_active,
                "kind": classify_recurring_kind(last["description"]),
            }
        )

    charges.sort(key=lambda c: -c["amount"])
    return charges
