"""Tests for SubscriptionMatcher — upcoming generation, auto-match, staleness, cancel."""

import pytest
from datetime import datetime, timedelta
from src.storage import Storage
from src.subscriptions import SubscriptionMatcher, compute_next_billing_date


@pytest.fixture
def storage(in_memory_db):
    return Storage(in_memory_db)


@pytest.fixture
def sub_id(storage):
    return storage.create_subscription(
        merchant="Spotify", frequency="monthly", billing_day=15, label="Spotify Premium"
    )


class TestComputeNextBillingDate:
    def test_monthly_billing_day_past(self):
        # From 2026-04-20, billing_day=15 → next 15th is 2026-05-15
        result = compute_next_billing_date("monthly", 15, last_date="2026-04-20")
        assert result == "2026-05-15"

    def test_monthly_billing_day_not_yet_passed(self):
        # From 2026-05-10, billing_day=15 → still 2026-05-15
        result = compute_next_billing_date("monthly", 15, last_date="2026-05-10")
        assert result == "2026-05-15"

    def test_monthly_no_billing_day(self):
        result = compute_next_billing_date("monthly", None, last_date="2026-04-15")
        assert result == "2026-05-15"

    def test_annual_billing_day(self):
        result = compute_next_billing_date("annual", 15, last_date="2025-03-15")
        assert result == "2026-03-15"

    def test_weekly_billing_day(self):
        # billing_day=0 (Monday), from 2026-05-05 (Tuesday) → 2026-05-11 (next Monday)
        result = compute_next_billing_date("weekly", 0, last_date="2026-05-05")
        assert result == "2026-05-11"


class TestUpcomingGeneration:
    def test_generates_upcoming_for_active_subscription(self, storage, sub_id):
        matcher = SubscriptionMatcher(storage)
        matcher.run()
        upcoming = storage.list_upcoming_transactions(sub_id)
        assert len(upcoming) >= 1
        assert upcoming[0]["status"] == "pending"

    def test_does_not_duplicate_upcoming(self, storage, sub_id):
        matcher = SubscriptionMatcher(storage)
        matcher.run()
        matcher.run()
        upcoming = storage.list_upcoming_transactions(sub_id)
        pending = [u for u in upcoming if u["status"] == "pending"]
        assert len(pending) == 1

    def test_does_not_generate_for_cancelled_subscription(self, storage, sub_id):
        storage.update_subscription(sub_id, status="cancelled")
        matcher = SubscriptionMatcher(storage)
        matcher.run()
        upcoming = storage.list_upcoming_transactions(sub_id)
        assert len(upcoming) == 0


class TestAutoMatch:
    def test_auto_matches_transaction_in_window(self, storage, sub_id, in_memory_db):
        expected_date = "2026-05-15"
        storage.create_upcoming_transaction(sub_id, expected_date, expected_amount=13.98)
        in_memory_db.execute(
            """INSERT INTO transactions
               (source, source_id, amount, currency, exchange_rate, merchant,
                category, transaction_date, type)
               VALUES ('apple_wallet', 'test-spotify-01', 13.98, 'SGD', 1.0,
                       'Spotify', 'Entertainment', '2026-05-15T10:00:00', 'expense')"""
        )
        in_memory_db.commit()

        SubscriptionMatcher(storage).run()
        upcoming = storage.list_upcoming_transactions(sub_id)
        assert upcoming[0]["status"] == "matched"
        assert upcoming[0]["matched_transaction_id"] is not None

    def test_does_not_match_outside_window(self, storage, sub_id, in_memory_db):
        expected_date = "2026-05-15"
        storage.create_upcoming_transaction(sub_id, expected_date, expected_amount=13.98)
        in_memory_db.execute(
            """INSERT INTO transactions
               (source, source_id, amount, currency, exchange_rate, merchant,
                category, transaction_date, type)
               VALUES ('apple_wallet', 'test-spotify-02', 13.98, 'SGD', 1.0,
                       'Spotify', 'Entertainment', '2026-05-05T10:00:00', 'expense')"""
        )
        in_memory_db.commit()

        SubscriptionMatcher(storage).run()
        upcoming = storage.list_upcoming_transactions(sub_id)
        assert upcoming[0]["status"] == "pending"


class TestStalenessDetection:
    def test_marks_possibly_cancelled_when_overdue(self, storage, sub_id, in_memory_db):
        old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        upcoming_id = storage.create_upcoming_transaction(sub_id, old_date, 13.98)
        in_memory_db.execute(
            """INSERT INTO transactions
               (source, source_id, amount, currency, exchange_rate, merchant,
                category, transaction_date, type)
               VALUES ('apple_wallet', 'test-spotify-03', 13.98, 'SGD', 1.0,
                       'Spotify', 'Entertainment', ?, 'expense')""",
            (old_date + "T10:00:00",),
        )
        in_memory_db.commit()
        tx = in_memory_db.execute(
            "SELECT id FROM transactions WHERE source_id = 'test-spotify-03'"
        ).fetchone()
        storage.match_upcoming_transaction(upcoming_id, tx["id"])

        SubscriptionMatcher(storage).run()
        sub = storage.get_subscription(sub_id)
        assert sub["status"] == "possibly_cancelled"

    def test_does_not_flag_active_subscription(self, storage, sub_id, in_memory_db):
        recent = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        upcoming_id = storage.create_upcoming_transaction(sub_id, recent, 13.98)
        in_memory_db.execute(
            """INSERT INTO transactions
               (source, source_id, amount, currency, exchange_rate, merchant,
                category, transaction_date, type)
               VALUES ('apple_wallet', 'test-spotify-04', 13.98, 'SGD', 1.0,
                       'Spotify', 'Entertainment', ?, 'expense')""",
            (recent + "T10:00:00",),
        )
        in_memory_db.commit()
        tx = in_memory_db.execute(
            "SELECT id FROM transactions WHERE source_id = 'test-spotify-04'"
        ).fetchone()
        storage.match_upcoming_transaction(upcoming_id, tx["id"])

        SubscriptionMatcher(storage).run()
        sub = storage.get_subscription(sub_id)
        assert sub["status"] == "active"

    def test_skips_cancelled_subscription(self, storage, sub_id):
        storage.update_subscription(sub_id, status="cancelled")
        # cancelled subscriptions must not be touched by matcher
        SubscriptionMatcher(storage).run()
        sub = storage.get_subscription(sub_id)
        assert sub["status"] == "cancelled"
