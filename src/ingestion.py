import logging
from typing import Optional, Callable

from src.parsers.base import ParseResult
from src.storage import Storage

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Centralised transaction ingestion: dedup → exchange → categorize → store → recurring."""

    def __init__(
        self,
        storage: Storage,
        categorizer=None,
        exchange_service=None,
        detector=None,
        on_recurring_pattern: Optional[Callable[[str, str, float], None]] = None,
    ):
        self.storage = storage
        self.categorizer = categorizer
        self.exchange_service = exchange_service
        self._on_recurring_pattern = on_recurring_pattern
        # Allow injection of a RecurringDetector (or mock) for testing
        if detector is not None:
            self._detector = detector
        else:
            from src.recurring import RecurringDetector
            self._detector = RecurringDetector(storage)

    def ingest(self, result: ParseResult) -> Optional[dict]:
        """Persist a ParseResult and return the stored transaction dict, or None on dedup."""
        # Same-source dedup (content-hash source_id)
        if self.storage.source_id_exists(result.source_id):
            logger.debug("Same-source duplicate skipped: %s", result.source_id)
            return None

        # Cross-source dedup (10-minute window)
        dup = self.storage.find_cross_source_duplicate(
            result.merchant, result.amount, result.source
        )
        if dup:
            logger.info(
                "Cross-source duplicate skipped: %s %.2f matches existing %s (id=%s)",
                result.merchant, result.amount, dup["source"], dup["id"],
            )
            return None

        # Exchange rate
        exchange_rate = 1.0
        if self.exchange_service and result.currency != "SGD":
            exchange_rate = self.exchange_service.get_rate(result.currency)

        # Categorize — reload overrides from DB so web-dashboard changes are picked up
        category: Optional[str] = None
        match_source: str = "default"
        if self.categorizer:
            self.categorizer.reload_overrides(self.storage.get_merchant_overrides())
            category, match_source = self.categorizer.categorize(result.merchant)

        try:
            tx_id = self.storage.insert_transaction(
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
                tx_type=result.tx_type,
            )
        except ValueError:
            logger.debug("Duplicate source_id on insert (race): %s", result.source_id)
            return None

        logger.info("Stored transaction: %s $%.2f", result.merchant, result.amount)

        try:
            self.storage.auto_assign_to_active_trip(tx_id)
        except Exception as e:
            logger.warning("auto_assign_to_active_trip failed (best-effort): %s", e)

        try:
            rec = self._detector.detect_and_suggest(result.merchant, result.amount, tx_id)
            if rec and self._on_recurring_pattern:
                # Only suggest if no subscription already exists for this merchant
                if not self.storage.find_subscription_by_merchant(result.merchant):
                    self._on_recurring_pattern(
                        result.merchant, rec["frequency"], rec["avg_amount"]
                    )
        except Exception as e:
            logger.warning("Recurring suggestion failed (best-effort): %s", e)

        tx = self.storage.get_transaction(tx_id)
        if tx is not None:
            tx["_match_source"] = match_source
        return tx
