import calendar
import sqlite3
from datetime import datetime, timedelta, timezone, date
from typing import Optional

from src.config import local_now


def _get_budget_period(period: str) -> tuple[str, str]:
    """Return (start_date, end_date) for the current budget period as ISO strings."""
    today = date.today()
    if period == "monthly":
        return today.replace(day=1).isoformat(), today.isoformat()
    elif period == "weekly":
        monday = today - timedelta(days=today.weekday())
        return monday.isoformat(), today.isoformat()
    raise ValueError(f"Unknown period '{period}'. Must be 'monthly' or 'weekly'.")


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
                """INSERT INTO categories (name, keywords, icon, color)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                     keywords = excluded.keywords,
                     icon     = excluded.icon,
                     color    = excluded.color""",
                (cat["name"], cat["keywords"], cat["icon"], cat.get("color")),
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

    def get_merchant_ranking(self, start_date: str, end_date: str, limit: int = 10) -> list[dict]:
        rows = self.conn.execute(
            """SELECT merchant, COUNT(*) as visits, SUM(amount * exchange_rate) as total
               FROM transactions
               WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ?
               AND merchant IS NOT NULL AND (type IS NULL OR type = 'expense')
               GROUP BY merchant ORDER BY total DESC LIMIT ?""",
            (start_date, end_date, limit),
        ).fetchall()
        return [{"merchant": r["merchant"], "visits": r["visits"], "total": r["total"]} for r in rows]

    def get_average_daily(self, start_date: str, end_date: str) -> float:
        row = self.conn.execute(
            """SELECT COALESCE(SUM(amount * exchange_rate), 0) as total
               FROM transactions
               WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ?
               AND (type IS NULL OR type = 'expense')""",
            (start_date, end_date),
        ).fetchone()
        total = row["total"]
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        days = max((end - start).days + 1, 1)
        return total / days

    def get_trend(self, start_date: str, end_date: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT DATE(transaction_date) as date, SUM(amount * exchange_rate) as amount
               FROM transactions
               WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ?
               AND (type IS NULL OR type = 'expense')
               GROUP BY DATE(transaction_date) ORDER BY date""",
            (start_date, end_date),
        ).fetchall()
        return [{"date": r["date"], "amount": r["amount"]} for r in rows]

    def get_trend_by_category(self, start_date: str, end_date: str) -> list[dict]:
        rows = self.conn.execute(
            """SELECT DATE(transaction_date) as date,
                      COALESCE(category, 'Other') as category,
                      SUM(amount * exchange_rate) as amount
               FROM transactions
               WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ?
               AND (type IS NULL OR type = 'expense')
               GROUP BY DATE(transaction_date), COALESCE(category, 'Other')
               ORDER BY date""",
            (start_date, end_date),
        ).fetchall()
        by_date: dict[str, dict] = {}
        all_categories: set[str] = set()
        for r in rows:
            d = r["date"]
            cat = r["category"]
            all_categories.add(cat)
            if d not in by_date:
                by_date[d] = {"date": d}
            by_date[d][cat] = round(r["amount"], 2)
        # Gap-fill: every date must have an explicit None for every category that
        # has no spend that day.  Recharts connectNulls only skips null values —
        # missing keys are treated as undefined/0 and break line continuity.
        for row in by_date.values():
            for cat in all_categories:
                if cat not in row:
                    row[cat] = None
        return list(by_date.values())

    def get_period_comparison(self, current_start: str, current_end: str, prev_start: str, prev_end: str) -> dict:
        curr_rows = self.conn.execute(
            """SELECT category, SUM(amount * exchange_rate) as total FROM transactions
               WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ?
               AND (type IS NULL OR type = 'expense') GROUP BY category""",
            (current_start, current_end),
        ).fetchall()
        prev_rows = self.conn.execute(
            """SELECT category, SUM(amount * exchange_rate) as total FROM transactions
               WHERE DATE(transaction_date) >= ? AND DATE(transaction_date) <= ?
               AND (type IS NULL OR type = 'expense') GROUP BY category""",
            (prev_start, prev_end),
        ).fetchall()
        curr_by_cat = {r["category"] or "Uncategorized": r["total"] for r in curr_rows}
        prev_by_cat = {r["category"] or "Uncategorized": r["total"] for r in prev_rows}
        return {
            "current": {"total": sum(curr_by_cat.values()), "by_category": curr_by_cat},
            "previous": {"total": sum(prev_by_cat.values()), "by_category": prev_by_cat},
        }

    def get_categories(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM categories ORDER BY ROWID").fetchall()
        return [dict(r) for r in rows]

    def get_category_icon_map(self) -> dict[str, str]:
        """Returns {category_name: icon} for all categories that have an icon."""
        rows = self.conn.execute(
            "SELECT name, icon FROM categories WHERE icon IS NOT NULL"
        ).fetchall()
        return {row["name"]: row["icon"] for row in rows}

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

    def source_id_exists(self, source_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM transactions WHERE source_id = ?", (source_id,)
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

    def add_category(self, name: str, keywords: str, icon: str = "📌", color: Optional[str] = None, cat_type: str = "neutral") -> None:
        existing = self.conn.execute("SELECT 1 FROM categories WHERE name = ?", (name,)).fetchone()
        if existing:
            raise ValueError(f"category '{name}' already exists")
        if color:
            clash = self.conn.execute("SELECT name FROM categories WHERE color = ? AND name != ?", (color, name)).fetchone()
            if clash:
                raise ValueError(f"color '{color}' is already used by category '{clash['name']}'")
        _VALID_TYPES = {"needs", "wants", "neutral"}
        if cat_type not in _VALID_TYPES:
            raise ValueError(f"cat_type must be one of {_VALID_TYPES}, got '{cat_type}'")
        self.conn.execute("INSERT INTO categories (name, keywords, icon, color, type) VALUES (?, ?, ?, ?, ?)", (name, keywords, icon, color, cat_type))
        self.conn.commit()

    def update_category(self, name: str, keywords: Optional[str] = None, icon: Optional[str] = None, color: Optional[str] = None, cat_type: Optional[str] = None) -> None:
        existing = self.conn.execute("SELECT 1 FROM categories WHERE name = ?", (name,)).fetchone()
        if not existing:
            raise ValueError(f"category '{name}' not found")
        if color:
            clash = self.conn.execute("SELECT name FROM categories WHERE color = ? AND name != ?", (color, name)).fetchone()
            if clash:
                raise ValueError(f"color '{color}' is already used by category '{clash['name']}'")
        updates = []
        params: list = []
        if keywords is not None:
            updates.append("keywords = ?")
            params.append(keywords)
        if icon is not None:
            updates.append("icon = ?")
            params.append(icon)
        if color is not None:
            updates.append("color = ?")
            params.append(color)
        if cat_type is not None:
            _VALID_TYPES = {"needs", "wants", "neutral"}
            if cat_type not in _VALID_TYPES:
                raise ValueError(f"cat_type must be one of {_VALID_TYPES}, got '{cat_type}'")
            updates.append("type = ?")
            params.append(cat_type)
        if not updates:
            return
        params.append(name)
        self.conn.execute(f"UPDATE categories SET {', '.join(updates)} WHERE name = ?", params)
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

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return default
        return row["value"]

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """INSERT INTO app_settings (key, value, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
               updated_at = excluded.updated_at""",
            (key, value),
        )
        self.conn.commit()

    def get_merchant_list(
        self,
        sort_by: str = "total_spent",
        tag_filter: str | None = None,
        category_filter: str | None = None,
        name_search: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> list[dict]:
        """Return paginated merchant list with computed stats and tags."""
        sort_map = {
            "total_spent":       "total_sgd DESC",
            "transaction_count": "transaction_count DESC",
            "last_seen":         "last_seen DESC",
            "merchant_name":     "ms.merchant ASC",
        }
        order = sort_map.get(sort_by, "total_sgd DESC")

        conditions = ["t.merchant IS NOT NULL", "(t.type IS NULL OR t.type = 'expense')"]
        params: list = []

        if name_search:
            conditions.append("t.merchant LIKE ?")
            params.append(f"%{name_search}%")
        if category_filter:
            conditions.append("t.category = ?")
            params.append(category_filter)

        where = " AND ".join(conditions)

        rows = self.conn.execute(
            f"""
            WITH merchant_stats AS (
                SELECT
                    t.merchant,
                    ROUND(SUM(t.amount * t.exchange_rate), 2) as total_sgd,
                    COUNT(*) as transaction_count,
                    ROUND(AVG(t.amount * t.exchange_rate), 2) as avg_amount_sgd,
                    DATE(MIN(t.transaction_date)) as first_seen,
                    DATE(MAX(t.transaction_date)) as last_seen
                FROM transactions t
                WHERE {where}
                GROUP BY t.merchant
            ),
            merchant_category AS (
                SELECT merchant, category,
                       ROW_NUMBER() OVER (PARTITION BY merchant ORDER BY COUNT(*) DESC) as rn
                FROM transactions
                WHERE merchant IS NOT NULL AND (type IS NULL OR type = 'expense') AND category IS NOT NULL
                GROUP BY merchant, category
            )
            SELECT
                ms.*,
                mc.category,
                COALESCE(mt.tags, '') as tags,
                COALESCE(mt.notes, '') as notes
            FROM merchant_stats ms
            LEFT JOIN merchant_category mc ON ms.merchant = mc.merchant AND mc.rn = 1
            LEFT JOIN merchant_tags mt ON ms.merchant = mt.merchant
            WHERE (? IS NULL OR ',' || COALESCE(mt.tags, '') || ',' LIKE '%,' || ? || ',%')
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            params + [tag_filter, tag_filter, limit, offset],
        ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
            result.append(d)
        return result

    def get_merchant_profile(self, merchant: str) -> dict | None:
        """Return full stats for a single merchant, or None if merchant has no transactions."""
        row = self.conn.execute(
            """
            SELECT
                t.merchant,
                ROUND(SUM(t.amount * t.exchange_rate), 2) as total_sgd,
                COUNT(*) as transaction_count,
                ROUND(AVG(t.amount * t.exchange_rate), 2) as avg_amount_sgd,
                DATE(MIN(t.transaction_date)) as first_seen,
                DATE(MAX(t.transaction_date)) as last_seen
            FROM transactions t
            WHERE t.merchant = ? AND (t.type IS NULL OR t.type = 'expense')
            """,
            (merchant,),
        ).fetchone()

        if not row or row["transaction_count"] == 0:
            return None

        profile = dict(row)
        tags_row = self.conn.execute(
            "SELECT tags, notes FROM merchant_tags WHERE merchant = ?", (merchant,)
        ).fetchone()
        profile["tags"] = []
        profile["notes"] = ""
        if tags_row:
            profile["tags"] = [t.strip() for t in (tags_row["tags"] or "").split(",") if t.strip()]
            profile["notes"] = tags_row["notes"] or ""
        return profile

    def get_merchant_tags(self, merchant: str) -> dict:
        """Return tags and notes for a merchant (empty defaults if not set)."""
        row = self.conn.execute(
            "SELECT tags, notes FROM merchant_tags WHERE merchant = ?", (merchant,)
        ).fetchone()
        if not row:
            return {"merchant": merchant, "tags": [], "notes": ""}
        return {
            "merchant": merchant,
            "tags": [t.strip() for t in (row["tags"] or "").split(",") if t.strip()],
            "notes": row["notes"] or "",
        }

    def set_merchant_tags(self, merchant: str, tags: list[str]) -> None:
        """Upsert tags for a merchant (does not touch notes)."""
        tags_str = ",".join(tags)
        self.conn.execute(
            """INSERT INTO merchant_tags (merchant, tags, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(merchant) DO UPDATE SET
                   tags = excluded.tags,
                   updated_at = excluded.updated_at""",
            (merchant, tags_str),
        )
        self.conn.commit()

    def set_merchant_notes(self, merchant: str, notes: str) -> None:
        """Upsert notes for a merchant (does not touch tags)."""
        self.conn.execute(
            """INSERT INTO merchant_tags (merchant, notes, updated_at)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(merchant) DO UPDATE SET
                   notes = excluded.notes,
                   updated_at = excluded.updated_at""",
            (merchant, notes),
        )
        self.conn.commit()

    def get_merchant_trend(self, merchant: str, months: int = 6) -> dict:
        """Return monthly spend totals for a merchant over the last N months."""
        rows = self.conn.execute(
            """
            SELECT strftime('%Y-%m', transaction_date) as month,
                   ROUND(SUM(amount * exchange_rate), 2) as total,
                   COUNT(*) as count
            FROM transactions
            WHERE merchant = ?
              AND (type IS NULL OR type = 'expense')
              AND transaction_date >= date('now', ? || ' months')
            GROUP BY month
            ORDER BY month ASC
            """,
            (merchant, f"-{months}"),
        ).fetchall()
        month_data = [dict(r) for r in rows]
        totals = [m["total"] for m in month_data]
        current = totals[-1] if totals else 0
        previous = totals[-2] if len(totals) >= 2 else 0
        if current > previous * 1.1:
            trend = "up"
        elif current < previous * 0.9:
            trend = "down"
        else:
            trend = "stable"
        return {
            "merchant": merchant,
            "months": month_data,
            "current_month": current,
            "previous_month": previous,
            "trend": trend,
        }

    # ── Budgets ────────────────────────────────────────────────────────────

    def create_budget(self, category: Optional[str], amount: float, period: str) -> int:
        if period not in ("monthly", "weekly"):
            raise ValueError(f"period must be 'monthly' or 'weekly', got '{period}'")
        # SQLite UNIQUE constraint doesn't fire for two NULLs, so check manually
        if category is None:
            existing = self.conn.execute(
                "SELECT 1 FROM budgets WHERE category IS NULL AND period = ?", (period,)
            ).fetchone()
            if existing:
                raise ValueError(f"Budget for 'Overall' ({period}) already exists")
        try:
            cursor = self.conn.execute(
                """INSERT INTO budgets (category, period, amount)
                   VALUES (?, ?, ?)""",
                (category, period, amount),
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            label = category if category else "Overall"
            raise ValueError(f"Budget for '{label}' ({period}) already exists")

    def get_budgets(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM budgets ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def update_budget(self, budget_id: int, amount: float) -> None:
        row = self.conn.execute("SELECT 1 FROM budgets WHERE id = ?", (budget_id,)).fetchone()
        if not row:
            raise ValueError(f"Budget {budget_id} not found")
        self.conn.execute(
            "UPDATE budgets SET amount = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (amount, budget_id),
        )
        self.conn.commit()

    def delete_budget(self, budget_id: int) -> None:
        row = self.conn.execute("SELECT 1 FROM budgets WHERE id = ?", (budget_id,)).fetchone()
        if not row:
            raise ValueError(f"Budget {budget_id} not found")
        self.conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        self.conn.commit()

    def get_budget_progress(self) -> list[dict]:
        """Return all budgets with current-period spending stats."""
        budgets = self.conn.execute("SELECT * FROM budgets ORDER BY id").fetchall()
        results = []
        today = date.today()

        for b in budgets:
            start, end = _get_budget_period(b["period"])

            if b["category"] is None:
                spent_row = self.conn.execute(
                    """SELECT COALESCE(SUM(amount * exchange_rate), 0) as total
                       FROM transactions
                       WHERE type = 'expense' AND DATE(transaction_date) BETWEEN ? AND ?""",
                    (start, end),
                ).fetchone()
            else:
                spent_row = self.conn.execute(
                    """SELECT COALESCE(SUM(amount * exchange_rate), 0) as total
                       FROM transactions
                       WHERE type = 'expense' AND category = ?
                         AND DATE(transaction_date) BETWEEN ? AND ?""",
                    (b["category"], start, end),
                ).fetchone()

            spent = spent_row["total"]
            budget_amount = b["amount"]
            remaining = budget_amount - spent
            percent = round(spent / budget_amount * 100, 1) if budget_amount > 0 else 0.0

            if b["period"] == "monthly":
                days_in_month = calendar.monthrange(today.year, today.month)[1]
                projected = round(spent / today.day * days_in_month, 2) if today.day > 0 else 0.0
            else:  # weekly
                weekday = today.weekday() + 1  # Mon = 1
                projected = round(spent / weekday * 7, 2) if weekday > 0 else 0.0

            status = (
                "over_budget" if percent >= 100
                else "warning" if percent >= 80
                else "on_track"
            )

            results.append({
                "id": b["id"],
                "category": b["category"],
                "label": b["category"] if b["category"] else "Overall",
                "period": b["period"],
                "budget_amount": budget_amount,
                "spent": round(spent, 2),
                "remaining": round(remaining, 2),
                "percent": percent,
                "projected": projected,
                "status": status,
                "period_start": start,
                "period_end": end,
            })
        return results

    # ── Goals ──────────────────────────────────────────────────────────────

    def create_goal(
        self,
        name: str,
        target_amount: float,
        target_date: Optional[str] = None,
    ) -> int:
        cursor = self.conn.execute(
            """INSERT INTO goals (name, target_amount, target_date)
               VALUES (?, ?, ?)""",
            (name, target_amount, target_date),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_goals(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM goals ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def update_goal(self, goal_id: int, **fields) -> None:
        allowed = {"name", "target_amount", "target_date", "status"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        row = self.conn.execute("SELECT 1 FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if not row:
            raise ValueError(f"Goal {goal_id} not found")
        set_clauses = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [goal_id]
        self.conn.execute(
            f"UPDATE goals SET {set_clauses}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        self.conn.commit()

    def delete_goal(self, goal_id: int) -> None:
        row = self.conn.execute("SELECT 1 FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if not row:
            raise ValueError(f"Goal {goal_id} not found")
        # ON DELETE CASCADE removes contributions automatically
        self.conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
        self.conn.commit()

    def add_contribution(
        self,
        goal_id: int,
        amount: float,
        month: str,
        source: str = "auto",
        note: Optional[str] = None,
        contributed_date: Optional[str] = None,
    ) -> int:
        if contributed_date is None:
            contributed_date = local_now().strftime("%Y-%m-%d")
        row = self.conn.execute("SELECT 1 FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if not row:
            raise ValueError(f"Goal {goal_id} not found")
        cursor = self.conn.execute(
            """INSERT INTO goal_contributions (goal_id, amount, month, contributed_date, source, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (goal_id, amount, month, contributed_date, source, note),
        )
        # Update saved_amount on the goal
        self.conn.execute(
            "UPDATE goals SET saved_amount = saved_amount + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (amount, goal_id),
        )
        # Auto-complete goal when saved_amount reaches or exceeds target_amount
        updated = self.conn.execute(
            "SELECT saved_amount, target_amount, status FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()
        if updated and updated["saved_amount"] >= updated["target_amount"] and updated["status"] == "active":
            self.conn.execute(
                "UPDATE goals SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (goal_id,),
            )
        self.conn.commit()
        return cursor.lastrowid

    def get_contributions(self, goal_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM goal_contributions WHERE goal_id = ? ORDER BY contributed_date ASC, month ASC",
            (goal_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_contribution(self, contribution_id: int, **fields) -> None:
        allowed = {"amount", "note", "contributed_date"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        row = self.conn.execute(
            "SELECT * FROM goal_contributions WHERE id = ?", (contribution_id,)
        ).fetchone()
        if not row:
            raise ValueError("Contribution not found")
        # If amount is changing, adjust the goal's saved_amount by the delta
        if "amount" in updates:
            delta = updates["amount"] - row["amount"]
            self.conn.execute(
                "UPDATE goals SET saved_amount = saved_amount + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (delta, row["goal_id"]),
            )
            # Re-evaluate completion status
            goal = self.conn.execute(
                "SELECT saved_amount, target_amount, status FROM goals WHERE id = ?", (row["goal_id"],)
            ).fetchone()
            if goal:
                if goal["saved_amount"] >= goal["target_amount"] and goal["status"] == "active":
                    self.conn.execute(
                        "UPDATE goals SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (row["goal_id"],),
                    )
                elif goal["saved_amount"] < goal["target_amount"] and goal["status"] == "completed":
                    self.conn.execute(
                        "UPDATE goals SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (row["goal_id"],),
                    )
        # Derive month from contributed_date if date is being updated
        if "contributed_date" in updates and updates["contributed_date"]:
            updates["month"] = updates["contributed_date"][:7]
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        self.conn.execute(
            f"UPDATE goal_contributions SET {set_clause} WHERE id = ?",
            (*updates.values(), contribution_id),
        )
        self.conn.commit()

    def delete_contribution(self, contribution_id: int) -> None:
        row = self.conn.execute(
            "SELECT * FROM goal_contributions WHERE id = ?", (contribution_id,)
        ).fetchone()
        if not row:
            raise ValueError("Contribution not found")
        self.conn.execute("DELETE FROM goal_contributions WHERE id = ?", (contribution_id,))
        self.conn.execute(
            "UPDATE goals SET saved_amount = MAX(0, saved_amount - ?), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (row["amount"], row["goal_id"]),
        )
        # If goal was completed but saved_amount now falls below target, revert to active
        goal = self.conn.execute(
            "SELECT saved_amount, target_amount, status FROM goals WHERE id = ?", (row["goal_id"],)
        ).fetchone()
        if goal and goal["saved_amount"] < goal["target_amount"] and goal["status"] == "completed":
            self.conn.execute(
                "UPDATE goals SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (row["goal_id"],),
            )
        self.conn.commit()

    def get_goal_progress(self, goal_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        if not row:
            return None
        goal = dict(row)
        contributions = self.get_contributions(goal_id)

        # Monthly rate: average of last 3 contributions
        recent = [c["amount"] for c in contributions[-3:]]
        monthly_rate = sum(recent) / len(recent) if recent else 0.0

        saved = goal["saved_amount"]
        target = goal["target_amount"]
        percent = round(saved / target * 100, 1) if target > 0 else 0.0
        remaining = target - saved
        months_to_target = round(remaining / monthly_rate, 1) if monthly_rate > 0 else None

        on_track = None
        if goal["target_date"] and months_to_target is not None:
            target_dt = datetime.strptime(goal["target_date"], "%Y-%m-%d")
            now = local_now()
            months_remaining = (target_dt.year - now.year) * 12 + (target_dt.month - now.month)
            if months_to_target < months_remaining * 0.9:
                on_track = "ahead"
            elif months_to_target <= months_remaining:
                on_track = "on_track"
            else:
                on_track = "behind"

        return {
            **goal,
            "percent": percent,
            "monthly_rate": round(monthly_rate, 2),
            "months_to_target": months_to_target,
            "on_track": on_track,
            "contributions": contributions,
        }

    def get_savings_overview(self, month: str) -> dict:
        """Return income, expenses, savings, and how much has been manually allocated to goals for the given month."""
        import calendar as _cal
        year, mon = int(month[:4]), int(month[5:7])
        last_day = _cal.monthrange(year, mon)[1]
        start = f"{month}-01"
        end = f"{month}-{last_day:02d}"

        income = self.conn.execute(
            """SELECT COALESCE(SUM(amount * exchange_rate), 0) as total
               FROM transactions WHERE type = 'income'
               AND DATE(transaction_date) BETWEEN ? AND ?""",
            (start, end),
        ).fetchone()["total"]
        expenses = self.conn.execute(
            """SELECT COALESCE(SUM(amount * exchange_rate), 0) as total
               FROM transactions WHERE (type IS NULL OR type = 'expense')
               AND DATE(transaction_date) BETWEEN ? AND ?""",
            (start, end),
        ).fetchone()["total"]
        savings = max(0.0, income - expenses)
        allocated = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM goal_contributions WHERE month = ?",
            (month,),
        ).fetchone()["total"]
        return {
            "month": month,
            "income": income,
            "expenses": expenses,
            "savings": savings,
            "allocated_to_goals": allocated,
            "unallocated": max(0.0, savings - allocated),
        }

    # ── Financial Health Score ──────────────────────────────────────────────

    def get_health_score(self, months: int = 1) -> dict:
        """Compute 0-100 financial health score using the 50/30/20 rule.

        Components (max pts):
          savings_rate      40  — min(savings_rate / 0.20, 1.0) × 40
          needs_ratio       20  — max(0, 1 − (needs_ratio − 0.50) / 0.50) × 20
          wants_ratio       20  — max(0, 1 − (wants_ratio − 0.30) / 0.30) × 20
          budget_adherence  10  — (budgets_within_limit / total_budgets) × 10
          anomaly_frequency 10  — max(0, 1 − anomaly_count / 5) × 10
        """
        from src.config import local_now

        now = local_now()
        period = now.strftime("%Y-%m")

        # Compute start date: first day N months back (months=1 → start of current month)
        year, month = now.year, now.month
        month -= months - 1
        while month <= 0:
            month += 12
            year -= 1
        start = f"{year}-{month:02d}-01"
        end = now.strftime("%Y-%m-%d")

        # ── Income ──────────────────────────────────────────────────────────
        income = self.conn.execute(
            """SELECT COALESCE(SUM(amount * exchange_rate), 0.0)
               FROM transactions WHERE type = 'income'
               AND DATE(transaction_date) BETWEEN ? AND ?""",
            (start, end),
        ).fetchone()[0]

        if income == 0:
            return {
                "has_income_data": False,
                "score": None,
                "grade": None,
                "components": {},
                "period": period,
            }

        # ── Total expenses ───────────────────────────────────────────────────
        total_expense = self.conn.execute(
            """SELECT COALESCE(SUM(amount * exchange_rate), 0.0)
               FROM transactions WHERE type = 'expense'
               AND DATE(transaction_date) BETWEEN ? AND ?""",
            (start, end),
        ).fetchone()[0]

        # ── Needs (expenses in categories with type='needs') ─────────────────
        needs = self.conn.execute(
            """SELECT COALESCE(SUM(t.amount * t.exchange_rate), 0.0)
               FROM transactions t
               LEFT JOIN categories c ON t.category = c.name
               WHERE t.type = 'expense'
               AND COALESCE(c.type, 'neutral') = 'needs'
               AND DATE(t.transaction_date) BETWEEN ? AND ?""",
            (start, end),
        ).fetchone()[0]

        # ── Wants (expenses in categories with type='wants') ─────────────────
        wants = self.conn.execute(
            """SELECT COALESCE(SUM(t.amount * t.exchange_rate), 0.0)
               FROM transactions t
               LEFT JOIN categories c ON t.category = c.name
               WHERE t.type = 'expense'
               AND COALESCE(c.type, 'neutral') = 'wants'
               AND DATE(t.transaction_date) BETWEEN ? AND ?""",
            (start, end),
        ).fetchone()[0]

        savings = income - total_expense
        savings_rate = savings / income
        needs_ratio = needs / income
        wants_ratio = wants / income

        # ── Component scores ────────────────────────────────────────────────
        savings_score = round(min(max(savings_rate, 0.0) / 0.20, 1.0) * 40, 1)
        needs_score = round(max(0.0, 1.0 - max(0.0, needs_ratio - 0.50) / 0.50) * 20, 1)
        wants_score = round(max(0.0, 1.0 - max(0.0, wants_ratio - 0.30) / 0.30) * 20, 1)

        # ── Budget adherence ────────────────────────────────────────────────
        budgets = self.get_budget_progress()
        if budgets:
            within = sum(1 for b in budgets if b["percent"] <= 100)
            budget_score = round((within / len(budgets)) * 10, 1)
            budget_adherence_value = round(within / len(budgets), 2)
        else:
            budget_score = 0.0
            budget_adherence_value = 0.0

        # ── Anomaly frequency ───────────────────────────────────────────────
        multiplier = float(self.get_setting("anomaly_multiplier", "2.0"))

        # Historical average per merchant (excluding current scoring period)
        merchant_avgs = {
            row["merchant"]: row["avg_amt"]
            for row in self.conn.execute(
                """SELECT merchant, AVG(amount * exchange_rate) as avg_amt
                   FROM transactions WHERE type = 'expense' AND merchant IS NOT NULL
                   AND DATE(transaction_date) < ?
                   GROUP BY merchant""",
                (start,),
            ).fetchall()
        }

        # Period transactions
        period_txs = self.conn.execute(
            """SELECT merchant, amount * exchange_rate as amt_sgd
               FROM transactions WHERE type = 'expense' AND merchant IS NOT NULL
               AND DATE(transaction_date) BETWEEN ? AND ?""",
            (start, end),
        ).fetchall()

        anomaly_count = sum(
            1
            for r in period_txs
            if r["merchant"] in merchant_avgs
            and merchant_avgs[r["merchant"]] > 0
            and r["amt_sgd"] > multiplier * merchant_avgs[r["merchant"]]
        )
        anomaly_score = round(max(0.0, 1.0 - anomaly_count / 5.0) * 10, 1)

        # ── Total and grade ─────────────────────────────────────────────────
        total_score = round(
            savings_score + needs_score + wants_score + budget_score + anomaly_score
        )
        grade = (
            "Excellent"       if total_score >= 80 else
            "Good"            if total_score >= 60 else
            "Fair"            if total_score >= 40 else
            "Needs Attention"
        )

        return {
            "score": total_score,
            "grade": grade,
            "has_income_data": True,
            "period": period,
            "components": {
                "savings_rate": {
                    "score": savings_score,
                    "max": 40,
                    "value": round(savings_rate, 3),
                    "benchmark": 0.20,
                    "label": "Savings Rate",
                    "description": "Percentage of income saved after all expenses",
                },
                "needs_ratio": {
                    "score": needs_score,
                    "max": 20,
                    "value": round(needs_ratio, 3),
                    "benchmark": 0.50,
                    "label": "Needs Ratio",
                    "description": "Essential spending (transport, groceries, bills) as % of income",
                },
                "wants_ratio": {
                    "score": wants_score,
                    "max": 20,
                    "value": round(wants_ratio, 3),
                    "benchmark": 0.30,
                    "label": "Wants Ratio",
                    "description": "Discretionary spending (dining, entertainment, shopping) as % of income",
                },
                "budget_adherence": {
                    "score": budget_score,
                    "max": 10,
                    "value": budget_adherence_value,
                    "label": "Budget Adherence",
                    "description": "Fraction of active budgets that are within their limit",
                },
                "anomaly_frequency": {
                    "score": anomaly_score,
                    "max": 10,
                    "value": anomaly_count,
                    "label": "Spending Anomalies",
                    "description": "Transactions significantly above your typical spend for that merchant",
                },
            },
        }
