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
    """RecurringDetector.run() should be called after a Gmail transaction is saved."""
    from unittest.mock import MagicMock, patch
    from src.storage import Storage
    from src.gmail_poller import GmailPoller
    from src.parsers.base import ParseResult

    storage = Storage(connection=in_memory_db)

    poller = GmailPoller(
        credentials_path="", token_path="", sender_filters=[],
        parsers=[], storage=storage, on_transaction=None,
    )

    mock_result = ParseResult(
        source="uob_paynow", source_id="newid123", amount=50.0,
        merchant="Netflix", transaction_date="2026-05-01T00:00:00",
    )

    with patch.object(storage, "insert_transaction", return_value=99), \
         patch("src.gmail_poller.RecurringDetector") as MockDetector:
        instance = MockDetector.return_value
        poller._save_and_detect(mock_result)
        instance.run.assert_called_once_with("Netflix", 50.0, 99)


def test_run_saves_recurring_when_pattern_detected(in_memory_db):
    """RecurringDetector.run must persist recurring record when pattern found."""
    storage = Storage(in_memory_db)

    for i in range(2):
        in_memory_db.execute("""
            INSERT INTO transactions (source, source_id, amount, currency, exchange_rate,
                merchant, category, transaction_date, type)
            VALUES ('manual', ?, 50.0, 'SGD', 1.0,
                'Netflix', 'Entertainment', ?, 'expense')
        """, (f"tx-recur-{i}", f"2026-0{i+1}-15T10:00:00"))
    in_memory_db.execute("""
        INSERT INTO transactions (source, source_id, amount, currency, exchange_rate,
            merchant, category, transaction_date, type)
        VALUES ('manual', 'tx-recur-new', 50.0, 'SGD', 1.0,
            'Netflix', 'Entertainment', '2026-03-15T10:00:00', 'expense')
    """)
    in_memory_db.commit()

    new_tx_id = in_memory_db.execute(
        "SELECT id FROM transactions WHERE source_id = 'tx-recur-new'"
    ).fetchone()["id"]

    detector = RecurringDetector(storage)
    detector.run("Netflix", 50.0, new_tx_id)

    rows = in_memory_db.execute(
        "SELECT * FROM recurring_transactions WHERE merchant = 'Netflix'"
    ).fetchall()
    assert len(rows) >= 1


def test_run_is_noop_when_no_pattern(in_memory_db):
    """RecurringDetector.run must not raise when no pattern is detected."""
    storage = Storage(in_memory_db)
    in_memory_db.execute("""
        INSERT INTO transactions (source, source_id, amount, currency, exchange_rate,
            merchant, category, transaction_date, type)
        VALUES ('manual', 'tx-once', 50.0, 'SGD', 1.0,
            'Random Shop', 'Other', '2026-04-15T10:00:00', 'expense')
    """)
    in_memory_db.commit()
    tx_id = in_memory_db.execute("SELECT id FROM transactions WHERE source_id='tx-once'").fetchone()["id"]

    detector = RecurringDetector(storage)
    detector.run("Random Shop", 50.0, tx_id)  # must not raise
