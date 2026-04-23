import hashlib
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
        # PayNow emails don't include a parseable transaction date, so we hash the full
        # body. This deduplicates re-delivered identical emails; slight footer variations
        # are acceptable because PayNow notifications are sent exactly once per transfer.
        source_id = hashlib.sha256(email_body.strip().encode()).hexdigest()[:16]
        return ParseResult(
            source="uob_paynow",
            source_id=source_id,
            amount=float(amount_str),
            merchant=recipient,
            description=email_body.strip(),
            raw_data=email_body,
        )
