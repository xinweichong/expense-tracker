import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.parsers.apple_wallet import AppleWalletParser
from src.storage import Storage

logger = logging.getLogger(__name__)


class AppleWalletPayload(BaseModel):
    amount: Optional[float] = None
    merchant: Optional[str] = None
    card_last4: Optional[str] = None
    date: Optional[str] = None


def create_webhook_app(storage: Storage) -> FastAPI:
    app = FastAPI()
    parser = AppleWalletParser()

    @app.post("/webhook/apple-wallet")
    async def receive_apple_wallet(payload: AppleWalletPayload):
        if payload.amount is None:
            raise HTTPException(status_code=400, detail="missing required field: amount")
        if not payload.merchant:
            raise HTTPException(status_code=400, detail="missing required field: merchant")

        # Dedup check
        if storage.recent_transaction_exists(payload.merchant, abs(payload.amount), minutes=5):
            return {"status": "duplicate", "transaction_id": None}

        try:
            result = parser.parse(payload.model_dump())
            tx_id = storage.insert_transaction(
                source=result.source,
                source_id=result.source_id,
                amount=result.amount,
                merchant=result.merchant,
                description=result.description,
                transaction_date=result.transaction_date,
                raw_data=result.raw_data,
            )
            return {"status": "ok", "transaction_id": tx_id}
        except Exception as e:
            logger.error(f"Webhook parse error: {e}")
            raise HTTPException(status_code=400, detail=str(e))

    return app
