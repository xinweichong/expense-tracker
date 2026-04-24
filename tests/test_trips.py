import pytest
from datetime import datetime
from src.storage import Storage


def _insert_tx(db, source_id, amount=50.0, merchant="TestMerchant", date="2026-04-15"):
    db.execute(
        """INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, merchant, category, transaction_date, type)
           VALUES ('test', ?, ?, 'SGD', 1.0, ?, 'Dining', ?, 'expense')""",
        (source_id, amount, merchant, date),
    )
    db.commit()
    return db.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestTripCRUD:
    def test_create_trip_minimal(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="Tokyo April", start_date="2026-04-10")
        assert isinstance(trip_id, int)
        trips = storage.get_trips()
        assert len(trips) == 1
        assert trips[0]["name"] == "Tokyo April"
        assert trips[0]["status"] == "inactive"
        assert trips[0]["destination"] is None

    def test_create_trip_full(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(
            name="Bali",
            start_date="2026-05-01",
            destination="Indonesia",
            primary_currency="IDR",
        )
        trips = storage.get_trips()
        assert trips[0]["destination"] == "Indonesia"
        assert trips[0]["primary_currency"] == "IDR"

    def test_get_trip_returns_single(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        trip = storage.get_trip(trip_id)
        assert trip is not None
        assert trip["id"] == trip_id

    def test_get_trip_unknown_returns_none(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        assert storage.get_trip(999) is None

    def test_update_trip_metadata(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="Old", start_date="2026-04-01")
        storage.update_trip(trip_id, name="New", destination="Japan")
        trip = storage.get_trip(trip_id)
        assert trip["name"] == "New"
        assert trip["destination"] == "Japan"

    def test_update_nonexistent_raises(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        with pytest.raises(ValueError):
            storage.update_trip(999, name="X")

    def test_delete_trip_removes_trip_transactions(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.enlist_transaction(trip_id, tx_id)
        storage.delete_trip(trip_id)
        assert storage.get_trips() == []
        rows = in_memory_db.execute("SELECT * FROM trip_transactions WHERE trip_id = ?", (trip_id,)).fetchall()
        assert len(rows) == 0

    def test_delete_nonexistent_raises(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        with pytest.raises(ValueError):
            storage.delete_trip(999)


class TestTripActivation:
    def test_activate_trip_sets_status_active(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        storage.activate_trip(trip_id)
        assert storage.get_trip(trip_id)["status"] == "active"

    def test_activate_deactivates_all_others(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        id1 = storage.create_trip(name="A", start_date="2026-04-01")
        id2 = storage.create_trip(name="B", start_date="2026-04-10")
        storage.activate_trip(id1)
        storage.activate_trip(id2)
        assert storage.get_trip(id1)["status"] == "inactive"
        assert storage.get_trip(id2)["status"] == "active"

    def test_only_one_active_at_a_time(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        ids = [storage.create_trip(name=f"T{i}", start_date="2026-04-01") for i in range(4)]
        for tid in ids:
            storage.activate_trip(tid)
        active = [storage.get_trip(tid) for tid in ids if storage.get_trip(tid)["status"] == "active"]
        assert len(active) == 1

    def test_deactivate_sets_inactive(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        storage.activate_trip(trip_id)
        storage.deactivate_trip(trip_id)
        assert storage.get_trip(trip_id)["status"] == "inactive"

    def test_get_active_trip_returns_active(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="Active", start_date="2026-04-01")
        storage.activate_trip(trip_id)
        active = storage.get_active_trip()
        assert active is not None
        assert active["id"] == trip_id

    def test_get_active_trip_returns_none_when_none(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        assert storage.get_active_trip() is None

    def test_activate_nonexistent_raises(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        with pytest.raises(ValueError):
            storage.activate_trip(999)


class TestTripTransactions:
    def test_enlist_transaction(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.enlist_transaction(trip_id, tx_id)
        txs = storage.get_trip_transactions(trip_id)
        assert len(txs) == 1
        assert txs[0]["id"] == tx_id

    def test_enlist_manual_sets_added_by(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.enlist_transaction(trip_id, tx_id, added_by="manual")
        row = in_memory_db.execute("SELECT added_by FROM trip_transactions").fetchone()
        assert row["added_by"] == "manual"

    def test_enlist_duplicate_is_idempotent(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.enlist_transaction(trip_id, tx_id)
        storage.enlist_transaction(trip_id, tx_id)  # should not raise
        assert len(storage.get_trip_transactions(trip_id)) == 1

    def test_delist_transaction(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.enlist_transaction(trip_id, tx_id)
        storage.delist_transaction(trip_id, tx_id)
        assert len(storage.get_trip_transactions(trip_id)) == 0

    def test_auto_assign_adds_to_active_trip(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        in_memory_db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('trips_enabled', 'true')")
        in_memory_db.commit()
        trip_id = storage.create_trip(name="Active Trip", start_date="2026-04-01")
        storage.activate_trip(trip_id)
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.auto_assign_to_active_trip(tx_id)
        assert len(storage.get_trip_transactions(trip_id)) == 1

    def test_auto_assign_no_op_when_disabled(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        # trips_enabled defaults to false
        trip_id = storage.create_trip(name="Active Trip", start_date="2026-04-01")
        storage.activate_trip(trip_id)
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.auto_assign_to_active_trip(tx_id)
        assert len(storage.get_trip_transactions(trip_id)) == 0

    def test_auto_assign_no_op_when_no_active_trip(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        in_memory_db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('trips_enabled', 'true')")
        in_memory_db.commit()
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.auto_assign_to_active_trip(tx_id)  # no active trip → no-op, no error

    def test_is_in_trip_true(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        tx_id = _insert_tx(in_memory_db, "t1")
        storage.enlist_transaction(trip_id, tx_id)
        assert storage.is_in_trip(trip_id, tx_id) is True

    def test_is_in_trip_false(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-01")
        tx_id = _insert_tx(in_memory_db, "t1")
        assert storage.is_in_trip(trip_id, tx_id) is False


class TestTripSummary:
    def test_summary_empty_trip(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="Empty", start_date="2026-04-01")
        summary = storage.get_trip_summary(trip_id)
        assert summary["total_sgd"] == 0.0
        assert summary["transaction_count"] == 0
        assert summary["daily_average_sgd"] == 0.0
        assert summary["by_category"] == []
        assert summary["by_day"] == []

    def test_summary_computes_total(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="Tokyo", start_date="2026-04-10")
        for i, amount in enumerate([100.0, 50.0, 75.0]):
            tx_id = _insert_tx(in_memory_db, f"t{i}", amount=amount, date="2026-04-10")
            storage.enlist_transaction(trip_id, tx_id)
        summary = storage.get_trip_summary(trip_id)
        assert summary["total_sgd"] == pytest.approx(225.0, abs=0.01)
        assert summary["transaction_count"] == 3

    def test_summary_by_category_sorted(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        trip_id = storage.create_trip(name="X", start_date="2026-04-10")
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, merchant, category, transaction_date, type) "
            "VALUES ('test', 'a', 200.0, 'SGD', 1.0, 'GrabFood', 'Dining', '2026-04-10', 'expense')"
        )
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, merchant, category, transaction_date, type) "
            "VALUES ('test', 'b', 80.0, 'SGD', 1.0, 'MRT', 'Transport', '2026-04-10', 'expense')"
        )
        in_memory_db.commit()
        tx_ids = [row[0] for row in in_memory_db.execute("SELECT id FROM transactions WHERE source_id IN ('a','b')").fetchall()]
        for tid in tx_ids:
            storage.enlist_transaction(trip_id, tid)
        summary = storage.get_trip_summary(trip_id)
        categories = [c["category"] for c in summary["by_category"]]
        assert "Dining" in categories
        assert "Transport" in categories
        assert summary["by_category"][0]["category"] == "Dining"

    def test_summary_unknown_trip_returns_none(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        assert storage.get_trip_summary(999) is None
