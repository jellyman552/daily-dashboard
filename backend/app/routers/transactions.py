"""Manual transaction entry + receipt scanning.

Adding or deleting a manual transaction triggers an immediate recompute of
the cached spending/budget snapshots (see app/services/refresh.py) instead
of waiting for the next scheduled refresh - the whole point of this feature
is seeing a purchase count right away.
"""
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas import ManualTransaction, ManualTransactionCreate, ReceiptParseResult
from app.services import manual_transactions, receipt_parser
from app.services.refresh import refresh_money

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/manual", response_model=list[ManualTransaction])
def list_manual_transactions():
    return manual_transactions.list_all()


@router.post("/manual", response_model=ManualTransaction, status_code=201)
def create_manual_transaction(body: ManualTransactionCreate):
    row = manual_transactions.add(
        date=body.date, amount=body.amount, description=body.description, category=body.category
    )
    try:
        refresh_money()
    except Exception:
        # The entry is saved either way; it'll show up on the next scheduled
        # refresh at worst - but this shouldn't fail silently.
        log.exception("manual transaction saved, but the live refresh failed")
    return row


@router.delete("/manual/{txn_id}", status_code=204)
def delete_manual_transaction(txn_id: str):
    if not manual_transactions.delete(txn_id):
        raise HTTPException(status_code=404, detail="No manual transaction with that id")
    try:
        refresh_money()
    except Exception:
        log.exception("manual transaction deleted, but the live refresh failed")


@router.post("/receipt/parse", response_model=ReceiptParseResult)
async def parse_receipt(file: UploadFile = File(...)):
    """Reads a receipt photo and returns a *draft* {date, amount, merchant} -
    nothing is saved. The frontend pre-fills the manual-entry form with this
    for you to review/edit, then submits it via POST /manual like any other
    entry."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Upload an image file")
    image_bytes = await file.read()
    try:
        return receipt_parser.parse_receipt(image_bytes, file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not parse receipt: {exc}") from exc
