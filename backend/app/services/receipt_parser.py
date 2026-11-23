"""Receipt photo -> {date, amount, merchant} via local OCR (Tesseract).

Free and fully local - no API key, no cloud service, nothing billed to
anyone. The tradeoff: raw OCR text has no understanding of receipt layout,
so pulling out the right numbers/date/merchant is regex-based guessing
rather than something that actually reads the receipt. Expect to correct
the draft sometimes, especially on angled/faded/crumpled photos - that's
exactly why this pre-fills the manual-entry form for review rather than
auto-saving it (see routers/transactions.py).

Setup: install the tesseract binary itself - pytesseract is just a thin
wrapper around it, and needs it present on PATH:
    macOS (local dev):  brew install tesseract
    Ubuntu (server):    sudo apt-get install -y tesseract-ocr
"""
import io
import re

import pytesseract
from PIL import Image

from app.localtime import local_today

# (regex, group order) - date group order varies by pattern.
_DATE_PATTERNS = [
    re.compile(r"\b(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{2,4})\b"),  # 8/30/2026, 08/30/26
    re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})\b"),  # 2026-08-30
]

_MONEY_RE = re.compile(r"\$?\s?(\d{1,4}\.\d{2})\b")
# Lines containing one of these (checked in order) are the best guess for
# where the real total lives, as opposed to a subtotal or a line item.
_TOTAL_LINE_KEYWORDS = ["grand total", "total due", "amount due", "balance due", "total"]


def _extract_date(text: str) -> str:
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            year = int(m.group("y"))
            if year < 100:
                year += 2000
            month, day = int(m.group("m")), int(m.group("d"))
            from datetime import date as _date

            return _date(year, month, day).isoformat()
        except ValueError:
            continue  # malformed match (OCR noise) - try the next pattern
    return local_today().isoformat()  # no readable date - best-effort fallback


def _extract_amount(text: str) -> float:
    for line in text.splitlines():
        lowered = line.lower()
        if "subtotal" in lowered:
            continue
        if any(kw in lowered for kw in _TOTAL_LINE_KEYWORDS):
            amounts = _MONEY_RE.findall(line)
            if amounts:
                return float(amounts[-1])
    # No line clearly says "total" - fall back to the largest dollar figure
    # in the whole receipt, since tax/tip/line items are usually smaller
    # than the final total.
    all_amounts = [float(a) for a in _MONEY_RE.findall(text)]
    return max(all_amounts) if all_amounts else 0.0


def _extract_merchant(text: str) -> str:
    # The store name is almost always one of the first few printed lines,
    # in the biggest text on the receipt - so just take the first line
    # that has enough real letters to plausibly be a name, not a phone
    # number, address fragment, or OCR noise.
    for line in text.splitlines():
        cleaned = line.strip()
        if re.search(r"[A-Za-z]{3,}", cleaned):
            return cleaned
    return "Unknown merchant"


def parse_receipt(image_bytes: bytes, media_type: str) -> dict:  # noqa: ARG001 - media_type kept for interface symmetry with the router
    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image)

    return {
        "date": _extract_date(text),
        "amount": round(_extract_amount(text), 2),
        "merchant": _extract_merchant(text),
    }
