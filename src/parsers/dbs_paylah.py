import re
from typing import Optional
from src.parsers.base import BankParser, ParseResult


class DbsPaylahParser(BankParser):
    sender_domain = "dbs.com"

    PAYMENT_PATTERN = re.compile(
        r"payment of \$([0-9,]+\.\d{2})\s+to\s+(.+?)(?:\.\s*Ref:|$)",
        re.IGNORECASE,
    )

    def can_parse(self, sender: str, subject: str) -> bool:
        return self.sender_domain in sender.lower()

    def parse(self, email_body: str) -> Optional[ParseResult]:
        match = self.PAYMENT_PATTERN.search(email_body)
        if not match:
            return None
        amount_str = match.group(1).replace(",", "")
        merchant = match.group(2).strip().rstrip(".")
        return ParseResult(
            source="dbs_paylah",
            source_id=None,
            amount=float(amount_str),
            merchant=merchant,
            description=email_body.strip(),
            raw_data=email_body,
        )
