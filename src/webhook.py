import logging
from typing import Optional, Callable
from fastapi import FastAPI, HTTPException
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, field_validator

from src.parsers.apple_wallet import AppleWalletParser

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


def create_webhook_app(user_manager, bot=None) -> FastAPI:
    """Create the Apple Wallet webhook FastAPI app.

    user_manager: object with .get(username) → UserContext | None
    bot: optional TelegramBotService for first-transaction notification
    """
    app = FastAPI()
    parser = AppleWalletParser()

    @app.post("/webhook/apple-wallet/{username}")
    async def receive_apple_wallet(username: str, payload: AppleWalletPayload):
        ctx = user_manager.get(username)
        if ctx is None:
            raise HTTPException(status_code=404, detail="User not found")

        storage = ctx.storage
        # Resolve per-user pipeline from the poller if available
        pipeline = getattr(ctx.poller, "pipeline", None) if ctx.poller else None
        # Resolve categorizer and exchange service from context attributes
        categorizer = getattr(ctx, "categorizer", None)
        exchange_service = getattr(ctx, "exchange_service", None)

        if payload.amount is None:
            raise HTTPException(status_code=400, detail="missing required field: amount")
        if not payload.merchant:
            raise HTTPException(status_code=400, detail="missing required field: merchant")

        try:
            result = parser.parse(payload.model_dump())
        except Exception as e:
            logger.error(f"Webhook parse error: {e}")
            raise HTTPException(status_code=400, detail=str(e))

        if pipeline is None:
            from src.ingestion import IngestionPipeline
            pipeline = IngestionPipeline(storage, categorizer, exchange_service)
        tx_dict = await run_in_threadpool(pipeline.ingest, result)
        if tx_dict is None:
            event = storage.get_source_event(result.source, result.source_id)
            return {"status": "duplicate", "transaction_id": event["transaction_id"] if event else None}

        on_transaction = getattr(ctx, "on_transaction", None)
        if on_transaction:
            on_transaction(tx_dict["id"], result.amount, result.merchant,
                           tx_dict["category"], tx_dict["_match_source"], result.source)
        _maybe_notify_first_apple_wallet(storage, bot, username)
        return {"status": "ok", "transaction_id": tx_dict["id"]}

    return app


def _maybe_notify_first_apple_wallet(storage, bot, username: str) -> None:
    """Send a one-time Telegram notification when the first Apple Wallet tx arrives."""
    if bot is None:
        return
    try:
        count = storage._conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE source = 'apple_wallet'"
        ).fetchone()[0]
        if count == 1:
            bot.notify_text(
                "Apple Wallet is working — your first transaction just came through.",
                username,
            )
    except Exception as e:
        logger.warning("first-apple-wallet notification failed: %s", e)
