import pytest
from datetime import datetime, timedelta
import sqlite3
from src.storage import Storage
from src.analytics import (
    get_period_comparison,
    get_category_comparison,
)


def make_db():
    """Create an in-memory SQLite DB with the full schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT UNIQUE,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'SGD',
            exchange_rate REAL DEFAULT 1.0,
            merchant TEXT,
            description TEXT,
            category TEXT,
            transaction_date DATETIME,
            ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            raw_data TEXT,
            type TEXT DEFAULT 'expense'
        );
    """)
    return conn


@pytest.fixture
def db_with_transactions():
    """Create a DB with transactions across two months."""
    conn = make_db()
    storage = Storage(conn)
    now = datetime.now()
    last_month = now.replace(day=1) - timedelta(days=1)

    # This month: $300 food, $100 transport
    for i in range(3):
        storage.insert_transaction(
            source="manual", source_id=f"food-{i}-this", amount=100.0, merchant=f"Food place {i}",
            category="Food", transaction_date=now.strftime("%Y-%m-%d"),
        )
    storage.insert_transaction(
        source="manual", source_id="transport-this", amount=100.0, merchant="Taxi",
        category="Transport", transaction_date=now.strftime("%Y-%m-%d"),
    )

    # Last month: $200 food, $150 transport
    for i in range(2):
        storage.insert_transaction(
            source="manual", source_id=f"food-{i}-last", amount=100.0, merchant=f"Food place {i}",
            category="Food", transaction_date=last_month.strftime("%Y-%m-%d"),
        )
    storage.insert_transaction(
        source="manual", source_id="transport-last", amount=150.0, merchant="MRT",
        category="Transport", transaction_date=last_month.strftime("%Y-%m-%d"),
    )

    yield conn
    conn.close()


class TestPeriodComparison:
    def test_overall_comparison(self, db_with_transactions):
        result = get_period_comparison(
            db_with_transactions, period="month"
        )
        assert result["current_total"] == 400.0
        assert result["previous_total"] == 350.0
        assert result["change_percent"] == pytest.approx(14.29, abs=0.1)

    def test_category_comparison(self, db_with_transactions):
        result = get_category_comparison(
            db_with_transactions, period="month"
        )
        categories = {r["category"]: r for r in result}
        assert categories["Food"]["current"] == 300.0
        assert categories["Food"]["previous"] == 200.0
        assert categories["Food"]["change"] == 100.0

    def test_no_previous_data(self):
        conn = make_db()
        result = get_period_comparison(conn, period="month")
        assert result["previous_total"] == 0
        conn.close()
