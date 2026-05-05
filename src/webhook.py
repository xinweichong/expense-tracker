import logging
from typing import Optional, Callable
from fastapi import FastAPI, HTTPException
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

        if pipeline is not None:
            tx_dict = pipeline.ingest(result)
            if tx_dict is None:
                dup = storage.find_cross_source_duplicate(
                    result.merchant, result.amount, "apple_wallet"
                )
                dup_id = dup["id"] if dup else None
                return {"status": "duplicate", "transaction_id": dup_id}
            _maybe_notify_first_apple_wallet(storage, bot, username)
            return {"status": "ok", "transaction_id": tx_dict["id"]}

        # --- Direct ingestion path (no pipeline) ---
        if storage.source_id_exists(result.source_id):
            return {"status": "duplicate", "transaction_id": None}

        dup = storage.find_cross_source_duplicate(
            result.merchant, result.amount, "apple_wallet"
        )
        if dup:
            logger.info(
                f"Cross-source duplicate: apple_wallet matches existing {dup['source']} "
                f"(id={dup['id']})"
            )
            return {"status": "duplicate", "transaction_id": dup["id"]}

        exchange_rate = 1.0
        if exchange_service and result.currency != "SGD":
            exchange_rate = exchange_service.get_rate(result.currency)

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

        try:
            storage.auto_assign_to_active_trip(tx_id)
        except Exception as e:
            logger.warning("auto_assign_to_active_trip failed (best-effort): %s", e)

        # Legacy on_transaction support (used by old tests via ctx attribute)
        on_transaction = getattr(ctx, "on_transaction", None)
        if on_transaction:
            on_transaction(tx_id, result.amount, result.merchant, category, match_source, result.source)

        from src.recurring import RecurringDetector
        RecurringDetector(storage).run(result.merchant, result.amount, tx_id)

        _maybe_notify_first_apple_wallet(storage, bot, username)
        return {"status": "ok", "transaction_id": tx_id}

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
