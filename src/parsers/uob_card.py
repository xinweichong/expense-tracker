import re
from typing import Optional
from src.parsers.base import BankParser, ParseResult


class UobCardParser(BankParser):
    sender_domain = "uobgroup.com"

    CARD_PATTERN = re.compile(
        r"A transaction of SGD\s+([0-9,]+\.\d{2})\s+was made with your UOB Card ending (\d{4})\s+on\s+(\d{2}/\d{2}/\d{2})\s+at\s+(.+?)\s*\.\s*If unauthorised",
        re.IGNORECASE,
    )

    TRANSIT_PATTERN = re.compile(
        r"accumulated transit transactions of SGD\s+([0-9,]+\.\d{2})\s+has been billed to your UOB card ending (\d{4})\s+on\s+(\d{2}/\d{2}/\d{2})",
        re.IGNORECASE,
    )

    def can_parse(self, sender: str, subject: str) -> bool:
        return self.sender_domain in sender.lower()

    def parse(self, email_body: str) -> Optional[ParseResult]:
        match = self.CARD_PATTERN.search(email_body)
        if match:
            amount_str = match.group(1).replace(",", "")
            card_last4 = match.group(2)
            date_str = match.group(3)  # dd/MM/yy
            merchant = match.group(4).strip()
        else:
            match = self.TRANSIT_PATTERN.search(email_body)
            if not match:
                return None
            amount_str = match.group(1).replace(",", "")
            card_last4 = match.group(2)
            date_str = match.group(3)  # dd/MM/yy
            merchant = "Transit"

        # Convert dd/MM/yy to YYYY-MM-DD
        day, month, short_year = date_str.split("/")
        year = 2000 + int(short_year)
        iso_date = f"{year}-{month}-{day}"

        return ParseResult(
            source="uob_card",
            source_id=None,
            amount=float(amount_str),
            merchant=merchant,
            description=f"UOB Card *{card_last4} - {merchant}",
            transaction_date=f"{iso_date}T00:00:00",
            raw_data=email_body,
        )
