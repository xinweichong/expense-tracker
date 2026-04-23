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
        dates = [datetime(2026, 4, 17), datetime(2026, 4, 10), datetime(2026, 3, 1)]
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


def test_recurring_detector_called_after_gmail_ingest(in_memory_db):
    """RecurringDetector.detect() should be called after a Gmail transaction is saved."""
    from unittest.mock import MagicMock, patch
    from src.storage import Storage
    from src.gmail_poller import GmailPoller
    from src.parsers.base import ParseResult

    storage = Storage(connection=in_memory_db)
    # Pre-seed two matching transactions so detect() can find a pattern
    for i, d in enumerate(["2026-03-01", "2026-04-01"]):
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, merchant, transaction_date, type) "
            "VALUES ('uob_paynow', ?, 50.0, 'Netflix', ?, 'expense')",
            (f"old_{i}", d),
        )
    in_memory_db.commit()

    poller = GmailPoller(
        credentials_path="", token_path="", sender_filters=[],
        parsers=[], storage=storage, on_transaction=None,
    )

    mock_result = ParseResult(
        source="uob_paynow", source_id="newid123", amount=50.0,
        merchant="Netflix", transaction_date="2026-05-01T00:00:00",
    )

    with patch.object(storage, "insert_transaction", return_value=99) as mock_insert, \
         patch("src.gmail_poller.RecurringDetector") as MockDetector:
        instance = MockDetector.return_value
        instance.detect.return_value = {"frequency": "monthly", "avg_amount": 50.0, "occurrences": 3}
        poller._save_and_detect(mock_result)
        instance.detect.assert_called_once_with("Netflix", 50.0)
        from unittest.mock import ANY
        instance.save_recurring.assert_called_once_with("Netflix", 50.0, "monthly", ANY)
