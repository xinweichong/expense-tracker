import logging
from typing import Optional, Callable
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from src.parsers.apple_wallet import AppleWalletParser
from src.storage import Storage
from src.recurring import RecurringDetector

logger = logging.getLogger(__name__)


class AppleWalletPayload(BaseModel):
    amount: Optional[str] = None
    merchant: Optional[str] = None
    card: Optional[str] = None
    date: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount_to_str(cls, v):
        """Accept numeric JSON values as well as strings (e.g. 12.5 → '12.5')."""
        if v is None:
            return None
        return str(v)


def create_webhook_app(
    storage: Storage,
    exchange_service=None,
    categorizer=None,
    on_transaction: Optional[Callable[[int, float, str, Optional[str], str, str], None]] = None,
) -> FastAPI:
    app = FastAPI()
    parser = AppleWalletParser()

    @app.post("/webhook/apple-wallet")
    async def receive_apple_wallet(payload: AppleWalletPayload):
        if payload.amount is None:
            raise HTTPException(status_code=400, detail="missing required field: amount")
        if not payload.merchant:
            raise HTTPException(status_code=400, detail="missing required field: merchant")

        try:
            result = parser.parse(payload.model_dump())
        except Exception as e:
            logger.error(f"Webhook parse error: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        # Same-source dedup: source_id is a content hash of merchant+amount+date,
        # so identical re-fires from the iOS Shortcut produce the same source_id.
        if storage.source_id_exists(result.source_id):
            return {"status": "duplicate", "transaction_id": None}

        # Cross-source dedup (10-minute window)
        dup = storage.find_cross_source_duplicate(
            result.merchant, result.amount, "apple_wallet"
        )
        if dup:
            logger.info(
                f"Cross-source duplicate: apple_wallet matches existing {dup['source']} "
                f"(id={dup['id']})"
            )
            return {"status": "duplicate", "transaction_id": dup["id"]}

        # Exchange rate lookup (1.0 for SGD or when service unavailable)
        exchange_rate = 1.0
        if exchange_service and result.currency != "SGD":
            exchange_rate = exchange_service.get_rate(result.currency)

        # Categorize merchant — reload overrides fresh from DB so any changes
        # made via the web dashboard are always reflected on the next transaction.
        category, match_source = None, "default"
        if categorizer:
            categorizer.reload_overrides(storage.get_merchant_overrides())
            category, match_source = categorizer.categorize(result.merchant)

        tx_id = storage.insert_transaction(
            source=result.source,
            source_id=result.source_id,
            amount=result.amount,
            merchant=result.merchant,
            description=result.description,
            transaction_date=result.transaction_date,
            raw_data=result.raw_data,
            currency=result.currency,
            exchange_rate=exchange_rate,
            category=category,
        )

        storage.auto_assign_to_active_trip(tx_id)

        if on_transaction:
            on_transaction(tx_id, result.amount, result.merchant, category, match_source, result.source)

        # Run recurring detection (best-effort, non-blocking)
        try:
            detector = RecurringDetector(storage)
            rec = detector.detect(result.merchant, result.amount)
            if rec:
                tx = storage.get_transaction(tx_id)
                detector.save_recurring(
                    result.merchant, rec["avg_amount"], rec["frequency"],
                    tx.get("category") if tx else None
                )
        except Exception as e:
            logger.warning("Recurring detection failed for %s: %s", result.merchant, e)

        return {"status": "ok", "transaction_id": tx_id}

    return app
