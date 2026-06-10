import pytest
from datetime import datetime, timedelta
from src.recurring import RecurringDetector
from src.storage import Storage


@pytest.fixture
def detector(in_memory_db):
    storage = Storage(connection=in_memory_db)
    return RecurringDetector(storage)


class TestRecurringDetection:
    def test_no_match_with_fewer_than_2_transactions(self, detector, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, merchant, transaction_date) "
            "VALUES ('m', 'm1', 17.98, 'Netflix', '2026-04-17T12:00:00')"
        )
        in_memory_db.commit()
        result = detector.detect("Netflix", 17.98)
        assert result is None

    def test_detect_monthly_recurring(self, detector, in_memory_db):
        base = datetime(2026, 4, 17)
        for i in range(3):
            d = base - timedelta(days=30 * i)
            in_memory_db.execute(
                f"INSERT INTO transactions (source, source_id, amount, merchant, transaction_date) "
                f"VALUES ('m', 'm{i}', 17.98, 'Netflix', '{d.strftime('%Y-%m-%dT%H:%M:%S')}')"
            )
        in_memory_db.commit()
        result = detector.detect("Netflix", 17.98)
        assert result is not None
        assert result["frequency"] == "monthly"
        assert abs(result["avg_amount"] - 17.98) < 0.01

    def test_no_match_with_inconsistent_amounts(self, detector, in_memory_db):
        base = datetime(2026, 4, 17)
        amounts = [17.98, 50.00, 17.98]
        for i, amt in enumerate(amounts):
            d = base - timedelta(days=30 * i)
            in_memory_db.execute(
                f"INSERT INTO transactions (source, source_id, amount, merchant, transaction_date) "
                f"VALUES ('m', 'm{i}', {amt}, 'Shop', '{d.strftime('%Y-%m-%dT%H:%M:%S')}')"
            )
        in_memory_db.commit()
        result = detector.detect("Shop", 50.00)
        assert result is None

    def test_no_match_with_inconsistent_intervals(self, detector, in_memory_db):
        now = datetime.now()
        dates = [now, now - timedelta(days=7), now - timedelta(days=47)]
        for i, d in enumerate(dates):
            in_memory_db.execute(
                f"INSERT INTO transactions (source, source_id, amount, merchant, transaction_date) "
                f"VALUES ('m', 'm{i}', 10.0, 'Shop', '{d.strftime('%Y-%m-%dT%H:%M:%S')}')"
            )
        in_memory_db.commit()
        result = detector.detect("Shop", 10.0)
        assert result is None

    def test_detect_weekly_recurring(self, detector, in_memory_db):
        base = datetime(2026, 4, 17)
        for i in range(3):
            d = base - timedelta(days=7 * i)
            in_memory_db.execute(
                f"INSERT INTO transactions (source, source_id, amount, merchant, transaction_date) "
                f"VALUES ('m', 'm{i}', 5.50, 'Kopi', '{d.strftime('%Y-%m-%dT%H:%M:%S')}')"
            )
        in_memory_db.commit()
        result = detector.detect("Kopi", 5.50)
        assert result is not None
        assert result["frequency"] == "weekly"

    def test_detects_biweekly_pattern(self, detector, in_memory_db):
        """Transactions ~14 days apart should be classified as biweekly."""
        now = datetime.now()
        dates = [
            (now - timedelta(days=28)).strftime("%Y-%m-%d"),
            (now - timedelta(days=14)).strftime("%Y-%m-%d"),
            now.strftime("%Y-%m-%d"),
        ]
        for i, d in enumerate(dates):
            in_memory_db.execute(
                f"INSERT INTO transactions (source, source_id, amount, merchant, transaction_date) "
                f"VALUES ('m', 'sp{i}', 29.99, 'Spotify', '{d}')"
            )
        in_memory_db.commit()
        result = detector.detect("Spotify", 29.99)
        assert result is not None
        assert result["frequency"] == "biweekly"
