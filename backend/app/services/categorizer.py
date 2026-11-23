"""Very small keyword-based transaction categorizer.

SimpleFIN hands us raw bank transaction descriptions with no category (unlike
Plaid), so we bucket them ourselves. This is intentionally simple —
substring matching against a keyword list — rather than ML.

Two tiers of rules:
  - _BUILTIN_RULES below: generic, safe to commit (no personal specifics).
  - backend/data/custom_categories.json: your own overrides — landlord/
    property manager name, a specific gym, whatever your bank's transaction
    descriptions actually say. This file is gitignored (backend/data/* is)
    so personal details never end up in the repo. Format:
        {"Housing": ["your landlord's name"], "Fitness": ["planet fitness"]}
    Entries here are merged into the built-in rules (matched first).
"""
import json
from pathlib import Path

from app.config import get_settings

_BUILTIN_RULES: list[tuple[str, list[str]]] = [
    ("Groceries", ["grocery", "safeway", "trader joe", "whole foods", "kroger", "sprouts", "costco", "ralphs", "vons", "food 4 less", "sams club", "sam's club", "samsclub", "winco"]),
    ("Restaurants", ["restaur", "cafe", "coffee", "starbucks", "doordash", "grubhub", "uber eats", "postmates", "pizza", "chipotle", "mcdonald", "taco", "kfc", "chick-fil-a", "chick fil a", "panera", "subway", "wingstop", "popeyes", "shake shack", "in-n-out", "el pollo loco"]),
    ("Transportation", ["uber", "lyft", "shell", "chevron", "arco", "exxon", "gas station", "parking", "transit", "dmv", "o'reilly", "autozone", "fastrak"]),
    ("Entertainment", ["netflix", "spotify", "hulu", "disney+", "hbo", "steam", "playstation", "xbox", "movie", "amc", "ticketmaster", "cinemark", "regal cinemas", "arcade"]),
    ("Shopping", ["amazon", "target", "walmart", "best buy", "ebay", "etsy", "harbor freight", "ikea"]),
    ("Utilities", ["pg&e", "pge", "comcast", "xfinity", "at&t", "verizon", "t-mobile", "water dept", "electric"]),
    ("Health", ["pharmacy", "cvs", "walgreens", "kaiser", "doctor", "dental", "clinic"]),
    ("Pets", ["vca animal", "animal hosp", "veterinary", "petco", "petsmart", "banfield", "trupanion", "healthy paws", "chewy.com", "chewy"]),
    ("Travel", ["airlines", "airbnb", "hotel", "marriott", "delta", "southwest", "united air"]),
    ("Insurance", ["insurance", "ins prem", "progressive", "geico", "state farm", "allstate", "esurance", "liberty mutual", "farmers ins"]),
    ("Housing", ["rent", "property mgmt", "apartment", "renters ins"]),
    # "Car Payment" isn't listed here - it's entirely defined via
    # custom_categories.json since the payee is a personal loan, not a
    # generic merchant name.
    # Money moving between your own accounts (savings contributions, paying off
    # your own credit card, etc.) - not an expense, so excluded from spending
    # totals and recurring detection everywhere (see is_transfer() below).
    ("Transfer", ["transfer", "internet payment", "online payment", "e-payment", "epayment", "autopay", "bill pay", "billpay"]),
]


def _load_custom_rules() -> list[tuple[str, list[str]]]:
    path = Path(get_settings().data_dir) / "custom_categories.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return [(category, [kw.lower() for kw in keywords]) for category, keywords in data.items()]


def _keyword_matches(text: str, keyword: str) -> bool:
    """Substring match, but requires the keyword start at a word boundary -
    not merely be a random tail of some longer alphanumeric token.

    Example: a payment confirmation code ending in "...0dmv" would match
    the "dmv" keyword and get netted against Transportation, making an
    unrelated deposit look like negative gas spending. A
    trailing boundary isn't required, since several keywords (e.g.
    "restaur") deliberately match as a *prefix* of a longer word
    ("restaurant") or a bank's truncated field ("...RESTAUR").
    """
    start = 0
    while True:
        idx = text.find(keyword, start)
        if idx == -1:
            return False
        if idx == 0 or not text[idx - 1].isalnum():
            return True
        start = idx + 1


def categorize(description: str) -> str:
    text = description.lower()
    for category, keywords in _load_custom_rules() + _BUILTIN_RULES:
        if any(_keyword_matches(text, kw) for kw in keywords):
            return category
    return "Other"


def known_categories() -> list[str]:
    """Every category name currently in use (built-in + custom overrides +
    budget categories) - for populating a category picker in the frontend."""
    names = {category for category, _ in _BUILTIN_RULES if category != "Transfer"}
    names.update(category for category, _ in _load_custom_rules())
    budgets_path = Path(get_settings().data_dir) / "budgets.json"
    if budgets_path.exists():
        with open(budgets_path) as f:
            names.update(json.load(f).keys())
    names.add("Other")
    return sorted(names)


def is_transfer(description: str) -> bool:
    """True for a self-transfer (savings contribution, paying your own credit
    card, etc.) - not a real expense, so callers should exclude these from
    spending totals and recurring detection."""
    return categorize(description) == "Transfer"


# Default keyword identifying an income deposit (paycheck) among all the
# incoming transactions on an account - "payroll" is a near-universal ACH
# descriptor for a direct-deposit paycheck, so this works out of the box
# without needing to store an employer name anywhere. Override by creating
# backend/data/income_keywords.json (gitignored) with {"keywords": [...]}
# if your paycheck's description doesn't contain "payroll".
_INCOME_KEYWORDS_DEFAULT = ["payroll"]


def _load_income_keywords() -> list[str]:
    path = Path(get_settings().data_dir) / "income_keywords.json"
    if not path.exists():
        return _INCOME_KEYWORDS_DEFAULT
    with open(path) as f:
        data = json.load(f)
    return [kw.lower() for kw in data.get("keywords", _INCOME_KEYWORDS_DEFAULT)]


def is_income(description: str) -> bool:
    """True for a deposit that looks like a paycheck (vs. a Zelle payment
    from a friend, a refund, a cashback credit, etc.)."""
    text = description.lower()
    return any(_keyword_matches(text, kw) for kw in _load_income_keywords())


# Categories that are obligations rather than discretionary services -
# used to split the recurring-charges list into "bills" vs "subscriptions".
_BILL_CATEGORIES = {"Housing", "Utilities", "Insurance", "Health", "Pets", "Car Payment"}

# Subscription-shaped merchants that don't cleanly fall under a spending
# category above (e.g. "Amazon" is Shopping for a one-off purchase, but
# "Amazon Prime" specifically is a subscription).
_SUBSCRIPTION_KEYWORDS = [
    "prime", "icloud", "apple.com/bill", "dropbox", "adobe", "membership",
    "subscription", "playstation plus", "xbox live", "audible", "patreon",
    "github", "notion", "1password", "youtube premium",
]


def classify_recurring_kind(description: str) -> str:
    """Buckets a recurring charge as "subscription", "bill", or "other" -
    reuses categorize() (custom overrides included), so e.g. a landlord
    name added to Housing in custom_categories.json flows through as a
    bill automatically."""
    category = categorize(description)
    if category == "Entertainment":
        return "subscription"
    if category in _BILL_CATEGORIES:
        return "bill"

    text = description.lower()
    if any(_keyword_matches(text, kw) for kw in _SUBSCRIPTION_KEYWORDS):
        return "subscription"
    return "other"
