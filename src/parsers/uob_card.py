import hashlib
import re
from typing import Optional
from src.parsers.base import BankParser, ParseResult

PATTERNS = [
    # Single card transaction
    (re.compile(
        r"A transaction of SGD\s+([0-9,]+\.\d{2})\s+was made with your UOB Card ending (\d{4})\s+on\s+(\d{2}/\d{2}/\d{2})\s+at\s+(.+?)\s*\.\s*If unauthorised",
        re.IGNORECASE,
    ), None),
    # Accumulated transit transaction
    (re.compile(
        r"accumulated transit transactions of SGD\s+([0-9,]+\.\d{2})\s+has been billed to your UOB card ending (\d{4})\s+on\s+(\d{2}/\d{2}/\d{2})",
        re.IGNORECASE,
    ), "Transit"),
]


class UobCardParser(BankParser):
    sender_domain = "uobgroup.com"

    def can_parse(self, sender: str, subject: str) -> bool:
        return self.sender_domain in sender.lower()

    def parse(self, email_body: str) -> Optional[ParseResult]:
        for pattern, fixed_merchant in PATTERNS:
            match = pattern.search(email_body)
            if not match:
                continue
            amount_str = match.group(1).replace(",", "")
            card_last4 = match.group(2)
            date_str = match.group(3)  # dd/MM/yy
            merchant = fixed_merchant or match.group(4).strip()
            # Convert dd/MM/yy to YYYY-MM-DD
            day, month, short_year = date_str.split("/")
            year = 2000 + int(short_year)
            iso_date = f"{year}-{month}-{day}"
            source_id = hashlib.sha256(
                f"{iso_date}:{amount_str}:{merchant}:{card_last4}".encode()
            ).hexdigest()[:16]
            return ParseResult(
                source="uob_card",
                source_id=source_id,
                amount=float(amount_str),
                merchant=merchant,
                description=f"UOB Card *{card_last4} - {merchant}",
                transaction_date=f"{iso_date}T00:00:00",
                raw_data=email_body,
            )
        return None
