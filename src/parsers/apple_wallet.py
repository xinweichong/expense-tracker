import hashlib
from datetime import datetime
from typing import Optional, Any
from src.parsers.base import BankParser, ParseResult


class AppleWalletParser(BankParser):
    sender_domain = ""  # Not email-based — receives webhook payloads

    DATE_FORMATS = ["%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]

    def can_parse(self, sender: str, subject: str) -> bool:
        return False  # Not used for email parsing

    def parse(self, payload: dict) -> Optional[ParseResult]:
        if "amount" not in payload:
            raise ValueError("missing required field: amount")
        if "merchant" not in payload:
            raise ValueError("missing required field: merchant")

        # Amount arrives as string from iOS Shortcut (e.g. "-12.50")
        # Negative = spending, positive = refund. Store as positive expense.
        amount = abs(float(str(payload["amount"]).strip().replace(",", "")))
        merchant = payload["merchant"]
        card_last4 = payload.get("card_last4", "")
        date_str = payload.get("date", "")
        source_id = hashlib.sha256(
            f"{merchant}:{amount}:{card_last4}:{date_str}".encode()
        ).hexdigest()[:16]

        # Parse date from Shortcut format (dd/MM/yyyy HH:mm:ss) to ISO format
        transaction_date = date_str
        for fmt in self.DATE_FORMATS:
            try:
                parsed = datetime.strptime(date_str, fmt)
                transaction_date = parsed.strftime("%Y-%m-%dT%H:%M:%S")
                break
            except (ValueError, TypeError):
                continue

        return ParseResult(
            source="apple_wallet",
            source_id=source_id,
            amount=amount,
            merchant=merchant,
            description=f"Apple Wallet - {card_last4}",
            transaction_date=transaction_date,
            raw_data=str(payload),
        )
