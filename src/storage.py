import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional


class Storage:
    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection
        self.conn.row_factory = sqlite3.Row

    def insert_transaction(
        self,
        source: str,
        source_id: str,
        amount: float,
        merchant: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        currency: str = "SGD",
        exchange_rate: float = 1.0,
        transaction_date: Optional[str] = None,
        raw_data: Optional[str] = None,
        tx_type: str = "expense",
    ) -> int:
        try:
            cursor = self.conn.execute(
                """INSERT INTO transactions
                   (source, source_id, amount, currency, exchange_rate, merchant, description,
                    category, transaction_date, raw_data, type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source, source_id, amount, currency, exchange_rate, merchant, description,
                 category, transaction_date, raw_data, tx_type),
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"duplicate source_id: {source_id}")

    def get_transaction(self, tx_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_transaction(self, tx_id: int, **fields) -> None:
        if not fields:
            return
        if self.get_transaction(tx_id) is None:
            raise ValueError(f"transaction {tx_id} not found")
        set_clauses = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [tx_id]
        self.conn.execute(
            f"UPDATE transactions SET {set_clauses} WHERE id = ?", values
        )
        self.conn.commit()

    def delete_transaction(self, tx_id: int) -> None:
        if self.get_transaction(tx_id) is None:
            raise ValueError(f"transaction {tx_id} not found")
        self.conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self.conn.commit()

    def query_transactions(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        source: Optional[str] = None,
        merchant_search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        conditions = []
        params = []
        if start_date:
            conditions.append("DATE(transaction_date) >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("DATE(transaction_date) <= ?")
            params.append(end_date)
        if category:
            conditions.append("category = ?")
            params.append(category)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if merchant_search:
            conditions.append("merchant LIKE ?")
            params.append(f"%{merchant_search}%")
        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self.conn.execute(
            f"SELECT * FROM transactions WHERE {where} "
            f"ORDER BY transaction_date DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return [dict(r) for r in rows]

    def get_spending_summary(
        self, start_date: str, end_date: str
    ) -> dict:
        rows = self.conn.execute(
            """SELECT category, SUM(amount * exchange_rate) as total
               FROM transactions
               WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ?
               AND (type IS NULL OR type = 'expense')
               GROUP BY category""",
            (start_date, end_date),
        ).fetchall()
        by_category = {r["category"] or "Uncategorized": r["total"] for r in rows}
        return {
            "total": sum(by_category.values()),
            "by_category": by_category,
        }

    def load_categories(self, categories: list[dict]) -> None:
        for cat in categories:
            self.conn.execute(
                """INSERT OR REPLACE INTO categories (name, keywords, icon)
                   VALUES (?, ?, ?)""",
                (cat["name"], cat["keywords"], cat["icon"]),
            )
        self.conn.commit()

    def get_income_summary(self, start_date: str, end_date: str) -> dict:
        rows = self.conn.execute(
            """SELECT category, SUM(amount * exchange_rate) as total
               FROM transactions
               WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ?
               AND type = 'income'
               GROUP BY category""",
            (start_date, end_date),
        ).fetchall()
        by_category = {r["category"] or "Uncategorized": r["total"] for r in rows}
        return {"total": sum(by_category.values()), "by_category": by_category}

    def get_balance(self, start_date: str, end_date: str) -> dict:
        expenses = self.get_spending_summary(start_date, end_date)["total"]
        income = self.get_income_summary(start_date, end_date)["total"]
        return {"income": income, "expenses": expenses, "net": income - expenses}

    def get_categories(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM categories ORDER BY ROWID").fetchall()
        return [dict(r) for r in rows]

    def get_ingestion_state(self, source: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM ingestion_state WHERE source = ?", (source,)
        ).fetchone()
        return dict(row) if row else None

    def update_ingestion_state(
        self, source: str, last_id: str, last_at: str
    ) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO ingestion_state
               (source, last_processed_id, last_processed_at, updated_at)
               VALUES (?, ?, ?, CURRENT_TIMESTAMP)""",
            (source, last_id, last_at),
        )
        self.conn.commit()

    def is_duplicate(self, source: str, source_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM transactions WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
        return row is not None

    def recent_transaction_exists(
        self, merchant: str, amount: float, minutes: int = 5
    ) -> bool:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        row = self.conn.execute(
            """SELECT 1 FROM transactions
               WHERE merchant = ? AND amount = ? AND ingested_at >= ?""",
            (merchant, amount, cutoff_str),
        ).fetchone()
        return row is not None

    def add_category(self, name: str, keywords: str, icon: str = "📌") -> None:
        existing = self.conn.execute("SELECT 1 FROM categories WHERE name = ?", (name,)).fetchone()
        if existing:
            raise ValueError(f"category '{name}' already exists")
        self.conn.execute("INSERT INTO categories (name, keywords, icon) VALUES (?, ?, ?)", (name, keywords, icon))
        self.conn.commit()

    def update_category(self, name: str, keywords: str) -> None:
        existing = self.conn.execute("SELECT 1 FROM categories WHERE name = ?", (name,)).fetchone()
        if not existing:
            raise ValueError(f"category '{name}' not found")
        self.conn.execute("UPDATE categories SET keywords = ? WHERE name = ?", (keywords, name))
        self.conn.commit()

    def delete_category(self, name: str) -> int:
        existing = self.conn.execute("SELECT 1 FROM categories WHERE name = ?", (name,)).fetchone()
        if not existing:
            raise ValueError(f"category '{name}' not found")
        count = self.conn.execute("UPDATE transactions SET category = 'Other' WHERE category = ?", (name,)).rowcount
        self.conn.execute("DELETE FROM merchant_overrides WHERE category = ?", (name,))
        self.conn.execute("DELETE FROM categories WHERE name = ?", (name,))
        self.conn.commit()
        return count

    def set_merchant_override(self, merchant: str, category: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO merchant_overrides (merchant, category, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (merchant, category),
        )
        self.conn.commit()

    def get_merchant_overrides(self) -> dict[str, str]:
        rows = self.conn.execute("SELECT merchant, category FROM merchant_overrides").fetchall()
        return {r["merchant"]: r["category"] for r in rows}

    def remove_merchant_override(self, merchant: str) -> None:
        self.conn.execute("DELETE FROM merchant_overrides WHERE merchant = ?", (merchant,))
        self.conn.commit()

    def find_cross_source_duplicate(
        self, merchant: str, amount: float, source: str, within_minutes: int = 10
    ) -> Optional[dict]:
        """Find a transaction from a different source with matching merchant and amount."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=within_minutes)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        row = self.conn.execute(
            """SELECT * FROM transactions
               WHERE amount = ? AND source != ? AND ingested_at >= ?
               AND LOWER(merchant) = LOWER(?)
               LIMIT 1""",
            (amount, source, cutoff, merchant),
        ).fetchone()
        return dict(row) if row else None
