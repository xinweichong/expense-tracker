import pytest
from datetime import datetime, timedelta
import sqlite3
from src.storage import Storage
from src.analytics import (
    get_period_comparison,
    get_category_comparison,
    get_top_merchants,
    get_merchant_trend,
    get_spending_velocity,
    get_anomalies,
    check_new_merchants,
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


class TestMerchantAnalysis:
    def test_top_merchants_by_spend(self, db_with_transactions):
        result = get_top_merchants(db_with_transactions, limit=5)
        assert len(result) > 0
        # First result should be highest spending merchant
        assert result[0]["total"] >= result[-1]["total"]
        assert "merchant" in result[0]
        assert "count" in result[0]
        assert "total" in result[0]

    def test_merchant_trend(self, db_with_transactions):
        result = get_merchant_trend(db_with_transactions, merchant="Food place 0")
        assert "current_month" in result
        assert "previous_month" in result
        assert result["current_month"] == 100.0
        assert result["previous_month"] == 100.0
        assert result["trend"] == "stable"
        assert isinstance(result["months"], list)

    def test_merchant_trend_unknown_merchant(self):
        conn = make_db()
        result = get_merchant_trend(conn, merchant="Nonexistent")
        assert result["current_month"] == 0
        assert result["previous_month"] == 0
        assert result["trend"] == "stable"
        assert result["months"] == []
        conn.close()

    def test_top_merchants_limit(self):
        conn = make_db()
        storage = Storage(conn)
        for i in range(10):
            storage.insert_transaction(
                source="manual", source_id=f"shop-{i}",
                amount=float(i + 1),
                merchant=f"Shop {i}", category="Shopping",
                transaction_date=datetime.now().strftime("%Y-%m-%d"),
            )
        result = get_top_merchants(conn, limit=3)
        assert len(result) == 3
        conn.close()


class TestSpendingVelocity:
    def test_velocity_calculation(self, db_with_transactions):
        result = get_spending_velocity(db_with_transactions)
        assert "current_mtd" in result
        assert "projected_total" in result
        assert "last_month_total" in result
        assert "pace_percent" in result
        assert result["current_mtd"] > 0

    def test_velocity_start_of_month(self):
        conn = make_db()
        storage = Storage(conn)
        today = datetime.now()
        first_day = today.replace(day=1).strftime("%Y-%m-%d")
        storage.insert_transaction(
            source="manual", source_id="vel-test-1", amount=50.0, merchant="Test",
            category="Food", transaction_date=first_day,
        )
        result = get_spending_velocity(conn)
        assert result["current_mtd"] == 50.0
        conn.close()


class TestAnomalies:
    def test_no_anomalies(self, db_with_transactions):
        result = get_anomalies(db_with_transactions)
        assert isinstance(result, list)

    def test_anomaly_detection(self):
        conn = make_db()
        storage = Storage(conn)
        # Normal transactions: $15 each in Food (5 of them, so avg = 15)
        for i in range(5):
            storage.insert_transaction(
                source="manual", source_id=f"normal-{i}",
                amount=15.0, merchant="Normal shop",
                category="Food", transaction_date=datetime.now().strftime("%Y-%m-%d"),
            )
        # Anomalous transaction: $500 in Food (> 2x average)
        storage.insert_transaction(
            source="manual", source_id="anomaly-1",
            amount=500.0, merchant="Fancy restaurant",
            category="Food", transaction_date=datetime.now().strftime("%Y-%m-%d"),
        )
        result = get_anomalies(conn)
        assert len(result) > 0
        assert result[0]["amount"] == 500.0
        conn.close()


class TestNewMerchants:
    def test_detect_new_merchant(self):
        conn = make_db()
        storage = Storage(conn)
        # Old merchant (last month)
        last_month = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d")
        storage.insert_transaction(
            source="manual", source_id="old-shop", amount=10.0, merchant="Old shop",
            category="Food", transaction_date=last_month,
        )
        # New merchant (this month, first time)
        storage.insert_transaction(
            source="manual", source_id="new-shop", amount=20.0, merchant="New shop",
            category="Food", transaction_date=datetime.now().strftime("%Y-%m-%d"),
        )
        result = check_new_merchants(conn)
        assert any(r["merchant"] == "New shop" for r in result)
        conn.close()

    def test_new_merchant_no_duplicates(self):
        conn = make_db()
        storage = Storage(conn)
        today = datetime.now().strftime("%Y-%m-%d")
        # Two transactions from same new merchant on same day
        storage.insert_transaction(
            source="manual", source_id="dup-1", amount=10.0, merchant="New shop",
            category="Food", transaction_date=today,
        )
        storage.insert_transaction(
            source="manual", source_id="dup-2", amount=20.0, merchant="New shop",
            category="Food", transaction_date=today,
        )
        result = check_new_merchants(conn)
        merchants = [r["merchant"] for r in result]
        assert merchants.count("New shop") == 1  # no duplicate
        conn.close()
