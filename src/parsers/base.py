from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class ParseResult:
    source: str
    source_id: str
    amount: float
    merchant: str
    description: Optional[str] = None
    transaction_date: Optional[str] = None
    raw_data: Optional[str] = None
    currency: str = "SGD"
    tx_type: str = "expense"


class BankParser(ABC):
    sender_domain: str

    @abstractmethod
    def can_parse(self, sender: str, subject: str) -> bool:
        ...

    @abstractmethod
    def parse(self, content: Any) -> Optional[ParseResult]:
        ...
