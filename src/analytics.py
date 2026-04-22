"""Analytics computation module — pure functions that query the transactions table."""

import sqlite3
from datetime import datetime, timedelta
from typing import Any


def _get_month_range(date_str: str | None = None):
    """Return (start, end) for the month containing date_str (or current month)."""
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        d = datetime.now()
    start = d.replace(day=1)
    if d.month == 12:
        end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _get_week_range(date_str: str | None = None):
    """Return (start, end) for the week containing date_str."""
    if date_str:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        d = datetime.now()
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _get_previous_period(start: str, end: str):
    """Return (prev_start, prev_end) for the previous period of the same type."""
    s = datetime.strptime(start, "%Y-%m-%d")
    e = datetime.strptime(end, "%Y-%m-%d")
    span = (e - s).days + 1
    prev_end = s - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)
    return prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d")


def _query_total(conn: sqlite3.Connection, start: str, end: str, category: str | None = None):
    """Query total spending for a date range, optionally filtered by category."""
    query = """
        SELECT COALESCE(SUM(amount * exchange_rate), 0) as total
        FROM transactions
        WHERE type = 'expense'
          AND transaction_date >= ? AND transaction_date <= ?
    """
    params: list[Any] = [start, end]
    if category:
        query += " AND category = ?"
        params.append(category)
    row = conn.execute(query, params).fetchone()
    return row["total"]


def get_period_comparison(
    conn: sqlite3.Connection, period: str = "month", date: str | None = None
) -> dict:
    """Compare current period spending to the previous period."""
    if period == "week":
        start, end = _get_week_range(date)
    else:
        start, end = _get_month_range(date)

    prev_start, prev_end = _get_previous_period(start, end)

    current_total = _query_total(conn, start, end)
    previous_total = _query_total(conn, prev_start, prev_end)

    change = current_total - previous_total
    change_percent = (change / previous_total * 100) if previous_total > 0 else (None if current_total > 0 else 0)

    return {
        "current_start": start,
        "current_end": end,
        "previous_start": prev_start,
        "previous_end": prev_end,
        "current_total": round(current_total, 2),
        "previous_total": round(previous_total, 2),
        "change": round(change, 2),
        "change_percent": round(change_percent, 1) if change_percent is not None else None,
    }


def get_category_comparison(
    conn: sqlite3.Connection, period: str = "month", date: str | None = None
) -> list[dict]:
    """Compare per-category spending between current and previous period."""
    if period == "week":
        start, end = _get_week_range(date)
    else:
        start, end = _get_month_range(date)

    prev_start, prev_end = _get_previous_period(start, end)

    # Get all categories with spending in either period
    categories = conn.execute(
        """SELECT DISTINCT category FROM transactions 
           WHERE type='expense' AND category IS NOT NULL
             AND transaction_date >= ? AND transaction_date <= ?""",
        [prev_start, end],
    ).fetchall()

    results = []
    for row in categories:
        cat = row["category"]
        current = _query_total(conn, start, end, cat)
        previous = _query_total(conn, prev_start, prev_end, cat)
        change = current - previous
        change_pct = (change / previous * 100) if previous > 0 else (None if current > 0 else 0)
        results.append({
            "category": cat,
            "current": round(current, 2),
            "previous": round(previous, 2),
            "change": round(change, 2),
            "change_percent": round(change_pct, 1) if change_pct is not None else None,
        })

    return sorted(results, key=lambda x: x["current"], reverse=True)


def get_top_merchants(
    conn: sqlite3.Connection, limit: int = 10, period: str = "month", date: str | None = None
) -> list[dict]:
    """Get top merchants by total spending in the current period."""
    if period == "week":
        start, end = _get_week_range(date)
    else:
        start, end = _get_month_range(date)

    rows = conn.execute(
        """
        SELECT merchant,
               COUNT(*) as count,
               ROUND(SUM(amount * exchange_rate), 2) as total,
               ROUND(AVG(amount * exchange_rate), 2) as avg_amount
        FROM transactions
        WHERE type = 'expense'
          AND merchant IS NOT NULL
          AND transaction_date >= ? AND transaction_date <= ?
        GROUP BY merchant
        ORDER BY total DESC
        LIMIT ?
        """,
        [start, end, limit],
    ).fetchall()

    return [dict(r) for r in rows]


def get_merchant_trend(
    conn: sqlite3.Connection, merchant: str
) -> dict:
    """Get spending trend for a specific merchant across months (ASC order for charting)."""
    rows = conn.execute(
        """
        SELECT strftime('%Y-%m', transaction_date) as month,
               ROUND(SUM(amount * exchange_rate), 2) as total,
               COUNT(*) as count
        FROM transactions
        WHERE type = 'expense' AND merchant = ?
        GROUP BY strftime('%Y-%m', transaction_date)
        ORDER BY month ASC
        LIMIT 6
        """,
        [merchant],
    ).fetchall()

    months = [dict(r) for r in rows]

    now = datetime.now()
    current_month_str = now.strftime("%Y-%m")
    if now.month == 1:
        prev_month_str = now.replace(year=now.year - 1, month=12).strftime("%Y-%m")
    else:
        prev_month_str = now.replace(month=now.month - 1).strftime("%Y-%m")

    months_by_key = {m["month"]: m["total"] for m in months}
    current_month = months_by_key.get(current_month_str, 0)
    previous_month = months_by_key.get(prev_month_str, 0)

    return {
        "merchant": merchant,
        "months": months,
        "current_month": current_month,
        "previous_month": previous_month,
        "trend": "up" if current_month > previous_month else ("down" if current_month < previous_month else "stable"),
    }
