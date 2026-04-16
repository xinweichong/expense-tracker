import re
from typing import Optional
from src.parsers.base import BankParser, ParseResult


class UobPaynowParser(BankParser):
    sender_domain = "uob.com"

    PAYNOW_PATTERN = re.compile(
        r"sent \$([0-9,]+\.\d{2})\s+via PayNow\s+to\s+(.+?)(?:\.\s*Transaction|$)",
        re.IGNORECASE,
    )

    def can_parse(self, sender: str, subject: str) -> bool:
        return self.sender_domain in sender.lower()

    def parse(self, email_body: str) -> Optional[ParseResult]:
        match = self.PAYNOW_PATTERN.search(email_body)
        if not match:
            return None
        amount_str = match.group(1).replace(",", "")
        recipient = match.group(2).strip().rstrip(".")
        return ParseResult(
            source="uob_paynow",
            source_id=None,
            amount=float(amount_str),
            merchant=recipient,
            description=email_body.strip(),
            raw_data=email_body,
        )
