import logging
from datetime import datetime
from typing import Optional
from src.storage import Storage

logger = logging.getLogger(__name__)


class RecurringDetector:
    def __init__(self, storage: Storage):
        self.storage = storage

    def detect(self, merchant: str, amount: float) -> Optional[dict]:
        rows = self.storage.conn.execute(
            """SELECT amount, transaction_date FROM transactions
               WHERE merchant = ? AND transaction_date >= date('now', '-90 days')
               AND (type IS NULL OR type = 'expense')
               ORDER BY transaction_date DESC""",
            (merchant,),
        ).fetchall()
        if len(rows) < 2:
            return None
        amounts = [r["amount"] for r in rows]
        avg_amount = sum(amounts) / len(amounts)
        if not all(abs(a - avg_amount) / avg_amount <= 0.10 for a in amounts):
            return None
        dates = []
        for r in rows:
            try:
                dates.append(datetime.strptime(r["transaction_date"][:10], "%Y-%m-%d"))
            except (ValueError, TypeError):
                continue
        dates.sort(reverse=True)
        if len(dates) < 2:
            return None
        intervals = [(dates[i] - dates[i + 1]).days for i in range(len(dates) - 1)]
        if not intervals:
            return None
        avg_interval = sum(intervals) / len(intervals)
        frequency = None
        if 25 <= avg_interval <= 35:
            frequency = "monthly"
        elif 6 <= avg_interval <= 8:
            frequency = "weekly"
        if not frequency:
            return None
        return {"frequency": frequency, "avg_amount": avg_amount, "occurrences": len(rows)}

    def save_recurring(self, merchant: str, avg_amount: float, frequency: str, category: Optional[str] = None) -> None:
        existing = self.storage.conn.execute(
            "SELECT id FROM recurring_transactions WHERE merchant = ?", (merchant,)
        ).fetchone()
        if existing:
            self.storage.conn.execute(
                """UPDATE recurring_transactions
                   SET avg_amount = ?, frequency = ?, category = ?, last_seen = CURRENT_TIMESTAMP,
                       occurrences = occurrences + 1 WHERE merchant = ?""",
                (avg_amount, frequency, category, merchant),
            )
        else:
            self.storage.conn.execute(
                """INSERT INTO recurring_transactions
                   (merchant, avg_amount, frequency, category, first_seen, last_seen, occurrences)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 2)""",
                (merchant, avg_amount, frequency, category),
            )
        self.storage.conn.commit()

    def get_all_recurring(self) -> list[dict]:
        rows = self.storage.conn.execute(
            "SELECT * FROM recurring_transactions ORDER BY avg_amount DESC"
        ).fetchall()
        return [dict(r) for r in rows]
