"""Build (or rebuild) the demo data: `DEMO_MODE=true python -m scripts.seed_demo`.
Wipes the data dir, writes demo budgets, and runs the normal refresh against
the fictional bank in app/services/demo.py."""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services import demo  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if __name__ == "__main__":
    if not get_settings().demo_mode:
        raise SystemExit("Refusing to run: set DEMO_MODE=true (this wipes the data directory).")
    raise SystemExit(demo.reset())
