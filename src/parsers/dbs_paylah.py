import re
from typing import Optional
from src.parsers.base import BankParser, ParseResult


class DbsPaylahParser(BankParser):
    sender_domain = "dbs.com"

    AMOUNT_PATTERN = re.compile(r"Amount:\s+SGD([0-9,]+\.\d{2})")
    MERCHANT_PATTERN = re.compile(r"To:\s+(.+?)(?:\s{2,}|$)", re.MULTILINE)
    REF_PATTERN = re.compile(r"Transaction Ref:\s+(\S+)")

    def can_parse(self, sender: str, subject: str) -> bool:
        return self.sender_domain in sender.lower()

    def parse(self, email_body: str) -> Optional[ParseResult]:
        amount_match = self.AMOUNT_PATTERN.search(email_body)
        merchant_match = self.MERCHANT_PATTERN.search(email_body)

        if not amount_match or not merchant_match:
            return None

        amount_str = amount_match.group(1).replace(",", "")
        merchant = merchant_match.group(1).strip()

        ref_match = self.REF_PATTERN.search(email_body)
        source_id = ref_match.group(1) if ref_match else None

        return ParseResult(
            source="dbs_paylah",
            source_id=source_id,
            amount=float(amount_str),
            merchant=merchant,
            description=email_body.strip(),
            raw_data=email_body,
        )
