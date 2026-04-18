import pytest
from datetime import datetime
from src.storage import Storage


@pytest.fixture
def storage(in_memory_db):
    return Storage(connection=in_memory_db)


class TestInsertTransaction:
    def test_insert_manual_transaction(self, storage):
        tx_id = storage.insert_transaction(
            source="manual",
            source_id="manual-20260416-001",
            amount=12.50,
            merchant="Toast Box",
            description="Lunch",
            transaction_date="2026-04-16T12:30:00",
        )
        assert tx_id == 1

    def test_insert_returns_id(self, storage):
        id1 = storage.insert_transaction(
            source="manual", source_id="m1", amount=5.0,
            merchant="Test", transaction_date="2026-04-16T12:00:00",
        )
        id2 = storage.insert_transaction(
            source="manual", source_id="m2", amount=10.0,
            merchant="Test2", transaction_date="2026-04-16T13:00:00",
        )
        assert id1 == 1
        assert id2 == 2

    def test_duplicate_source_id_raises(self, storage):
        storage.insert_transaction(
            source="dbs_paylah", source_id="email-123", amount=5.0,
            merchant="Test", transaction_date="2026-04-16T12:00:00",
        )
        with pytest.raises(ValueError, match="duplicate"):
            storage.insert_transaction(
                source="dbs_paylah", source_id="email-123", amount=5.0,
                merchant="Test", transaction_date="2026-04-16T12:00:00",
            )

    def test_insert_with_category(self, storage):
        tx_id = storage.insert_transaction(
            source="manual", source_id="m1", amount=12.50,
            merchant="Toast Box", category="Food",
            transaction_date="2026-04-16T12:00:00",
        )
        tx = storage.get_transaction(tx_id)
        assert tx["category"] == "Food"

    def test_insert_with_raw_data(self, storage):
        tx_id = storage.insert_transaction(
            source="dbs_paylah", source_id="e1", amount=5.0,
            merchant="Test", raw_data="original email body here",
            transaction_date="2026-04-16T12:00:00",
        )
        tx = storage.get_transaction(tx_id)
        assert tx["raw_data"] == "original email body here"


class TestGetTransaction:
    def test_get_existing(self, storage):
        tx_id = storage.insert_transaction(
            source="manual", source_id="m1", amount=12.50,
            merchant="Toast Box", transaction_date="2026-04-16T12:00:00",
        )
        tx = storage.get_transaction(tx_id)
        assert tx["merchant"] == "Toast Box"
        assert tx["amount"] == 12.50

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_transaction(999) is None


class TestUpdateTransaction:
    def test_update_merchant(self, storage):
        tx_id = storage.insert_transaction(
            source="manual", source_id="m1", amount=12.50,
            merchant="Toast Box", transaction_date="2026-04-16T12:00:00",
        )
        storage.update_transaction(tx_id, merchant="Ya Kun")
        tx = storage.get_transaction(tx_id)
        assert tx["merchant"] == "Ya Kun"

    def test_update_category(self, storage):
        tx_id = storage.insert_transaction(
            source="manual", source_id="m1", amount=12.50,
            merchant="Toast Box", category="Food",
            transaction_date="2026-04-16T12:00:00",
        )
        storage.update_transaction(tx_id, category="Transport")
        tx = storage.get_transaction(tx_id)
        assert tx["category"] == "Transport"

    def test_update_nonexistent_raises(self, storage):
        with pytest.raises(ValueError, match="not found"):
            storage.update_transaction(999, merchant="Test")


class TestDeleteTransaction:
    def test_delete_existing(self, storage):
        tx_id = storage.insert_transaction(
            source="manual", source_id="m1", amount=12.50,
            merchant="Toast Box", transaction_date="2026-04-16T12:00:00",
        )
        storage.delete_transaction(tx_id)
        assert storage.get_transaction(tx_id) is None

    def test_delete_nonexistent_raises(self, storage):
        with pytest.raises(ValueError, match="not found"):
            storage.delete_transaction(999)


class TestQueryTransactions:
    def test_query_by_date_range(self, storage):
        storage.insert_transaction(
            source="manual", source_id="m1", amount=10.0,
            merchant="A", transaction_date="2026-04-15T12:00:00",
        )
        storage.insert_transaction(
            source="manual", source_id="m2", amount=20.0,
            merchant="B", transaction_date="2026-04-16T12:00:00",
        )
        storage.insert_transaction(
            source="manual", source_id="m3", amount=30.0,
            merchant="C", transaction_date="2026-04-17T12:00:00",
        )
        results = storage.query_transactions(start_date="2026-04-16", end_date="2026-04-16")
        assert len(results) == 1
        assert results[0]["merchant"] == "B"

    def test_query_by_category(self, storage):
        storage.insert_transaction(
            source="manual", source_id="m1", amount=10.0,
            merchant="A", category="Food", transaction_date="2026-04-16T12:00:00",
        )
        storage.insert_transaction(
            source="manual", source_id="m2", amount=20.0,
            merchant="B", category="Transport", transaction_date="2026-04-16T12:00:00",
        )
        results = storage.query_transactions(category="Food")
        assert len(results) == 1
        assert results[0]["category"] == "Food"

    def test_query_by_merchant_search(self, storage):
        storage.insert_transaction(
            source="manual", source_id="m1", amount=10.0,
            merchant="Toast Box Jurong", transaction_date="2026-04-16T12:00:00",
        )
        storage.insert_transaction(
            source="manual", source_id="m2", amount=20.0,
            merchant="Ya Kun Clementi", transaction_date="2026-04-16T12:00:00",
        )
        results = storage.query_transactions(merchant_search="Toast")
        assert len(results) == 1
        assert "Toast" in results[0]["merchant"]

    def test_query_by_source(self, storage):
        storage.insert_transaction(
            source="dbs_paylah", source_id="d1", amount=10.0,
            merchant="A", transaction_date="2026-04-16T12:00:00",
        )
        storage.insert_transaction(
            source="uob_paynow", source_id="u1", amount=20.0,
            merchant="B", transaction_date="2026-04-16T12:00:00",
        )
        results = storage.query_transactions(source="dbs_paylah")
        assert len(results) == 1

    def test_query_spending_summary(self, storage):
        storage.insert_transaction(
            source="manual", source_id="m1", amount=10.0,
            merchant="A", category="Food", transaction_date="2026-04-16T12:00:00",
        )
        storage.insert_transaction(
            source="manual", source_id="m2", amount=20.0,
            merchant="B", category="Food", transaction_date="2026-04-16T13:00:00",
        )
        storage.insert_transaction(
            source="manual", source_id="m3", amount=30.0,
            merchant="C", category="Transport", transaction_date="2026-04-16T14:00:00",
        )
        summary = storage.get_spending_summary(
            start_date="2026-04-16", end_date="2026-04-16"
        )
        assert summary["total"] == 60.0
        assert summary["by_category"]["Food"] == 30.0
        assert summary["by_category"]["Transport"] == 30.0


class TestCategories:
    def test_load_categories(self, storage, sample_categories):
        storage.load_categories(sample_categories)
        cats = storage.get_categories()
        assert len(cats) == 6
        assert cats[0]["name"] == "Food"

    def test_load_categories_idempotent(self, storage, sample_categories):
        storage.load_categories(sample_categories)
        storage.load_categories(sample_categories)
        cats = storage.get_categories()
        assert len(cats) == 6


class TestIngestionState:
    def test_get_initial_state(self, storage):
        state = storage.get_ingestion_state("dbs_paylah")
        assert state is None

    def test_update_and_get_state(self, storage):
        storage.update_ingestion_state("dbs_paylah", "msg-123", "2026-04-16T12:00:00")
        state = storage.get_ingestion_state("dbs_paylah")
        assert state["last_processed_id"] == "msg-123"

    def test_update_state_overwrites(self, storage):
        storage.update_ingestion_state("dbs_paylah", "msg-123", "2026-04-16T12:00:00")
        storage.update_ingestion_state("dbs_paylah", "msg-456", "2026-04-16T13:00:00")
        state = storage.get_ingestion_state("dbs_paylah")
        assert state["last_processed_id"] == "msg-456"


class TestDuplicateCheck:
    def test_is_duplicate_false_for_new(self, storage):
        assert storage.is_duplicate("dbs_paylah", "email-123") is False

    def test_is_duplicate_true_after_insert(self, storage):
        storage.insert_transaction(
            source="dbs_paylah", source_id="email-123", amount=5.0,
            merchant="Test", transaction_date="2026-04-16T12:00:00",
        )
        assert storage.is_duplicate("dbs_paylah", "email-123") is True

    def test_recent_transaction_exists(self, storage):
        storage.insert_transaction(
            source="apple_wallet", source_id="aw-1", amount=12.50,
            merchant="Toast Box", transaction_date="2026-04-16T12:00:00",
        )
        assert storage.recent_transaction_exists("Toast Box", 12.50, minutes=5) is True

    def test_recent_transaction_not_exists_different_amount(self, storage):
        storage.insert_transaction(
            source="apple_wallet", source_id="aw-1", amount=12.50,
            merchant="Toast Box", transaction_date="2026-04-16T12:00:00",
        )
        assert storage.recent_transaction_exists("Toast Box", 99.99, minutes=5) is False


class TestCrossSourceDedup:
    def test_find_cross_source_duplicate_match(self, storage):
        storage.insert_transaction(
            source="apple_wallet", source_id="aw-1", amount=8.20,
            merchant="Ban Mian", transaction_date="2026-04-16T12:00:00",
        )
        result = storage.find_cross_source_duplicate(
            "Ban Mian", 8.20, "dbs_paylah"
        )
        assert result is not None
        assert result["source"] == "apple_wallet"
        assert result["amount"] == 8.20

    def test_find_cross_source_duplicate_case_insensitive(self, storage):
        storage.insert_transaction(
            source="apple_wallet", source_id="aw-1", amount=8.20,
            merchant="Ban Mian", transaction_date="2026-04-16T12:00:00",
        )
        result = storage.find_cross_source_duplicate(
            "BAN MIAN", 8.20, "dbs_paylah"
        )
        assert result is not None

    def test_find_cross_source_no_match_different_source(self, storage):
        storage.insert_transaction(
            source="dbs_paylah", source_id="db-1", amount=8.20,
            merchant="Ban Mian", transaction_date="2026-04-16T12:00:00",
        )
        result = storage.find_cross_source_duplicate(
            "Ban Mian", 8.20, "dbs_paylah"
        )
        assert result is None

    def test_find_cross_source_no_match_different_amount(self, storage):
        storage.insert_transaction(
            source="apple_wallet", source_id="aw-1", amount=8.20,
            merchant="Ban Mian", transaction_date="2026-04-16T12:00:00",
        )
        result = storage.find_cross_source_duplicate(
            "Ban Mian", 99.99, "dbs_paylah"
        )
        assert result is None

    def test_find_cross_source_no_match_old_transaction(self, storage):
        tx_id = storage.insert_transaction(
            source="apple_wallet", source_id="aw-1", amount=8.20,
            merchant="Ban Mian", transaction_date="2026-04-16T12:00:00",
        )
        # Override ingested_at to an old timestamp
        storage.conn.execute(
            "UPDATE transactions SET ingested_at = '2020-01-01 00:00:00' WHERE id = ?",
            (tx_id,),
        )
        storage.conn.commit()
        result = storage.find_cross_source_duplicate(
            "Ban Mian", 8.20, "dbs_paylah"
        )
        assert result is None


class TestCategoryCRUD:
    def test_add_category(self, storage):
        storage.add_category("Health", "clinic,pharmacy,guardian,watsons", "💊")
        cats = storage.get_categories()
        names = [c["name"] for c in cats]
        assert "Health" in names
        health = next(c for c in cats if c["name"] == "Health")
        assert health["keywords"] == "clinic,pharmacy,guardian,watsons"
        assert health["icon"] == "💊"

    def test_add_duplicate_category_raises(self, storage):
        storage.add_category("Food", "restaurant,cafe", "🍜")
        with pytest.raises(ValueError, match="already exists"):
            storage.add_category("Food", "other", "🍜")

    def test_update_category_keywords(self, storage):
        storage.add_category("Food", "restaurant,cafe", "🍜")
        storage.update_category("Food", "restaurant,cafe,kopitiam")
        cats = storage.get_categories()
        food = next(c for c in cats if c["name"] == "Food")
        assert "kopitiam" in food["keywords"]

    def test_update_nonexistent_category_raises(self, storage):
        with pytest.raises(ValueError, match="not found"):
            storage.update_category("Nonexistent", "keywords")

    def test_delete_category_reassigns_transactions(self, storage):
        storage.add_category("Food", "restaurant", "🍜")
        storage.add_category("Other", "", "📌")
        storage.insert_transaction(
            source="manual", source_id="m1", amount=10.0,
            merchant="Test", category="Food", transaction_date="2026-04-16T12:00:00",
        )
        storage.insert_transaction(
            source="manual", source_id="m2", amount=20.0,
            merchant="Test2", category="Food", transaction_date="2026-04-16T13:00:00",
        )
        count = storage.delete_category("Food")
        assert count == 2
        txs = storage.query_transactions(category="Other")
        assert len(txs) == 2
        cats = storage.get_categories()
        names = [c["name"] for c in cats]
        assert "Food" not in names

    def test_delete_nonexistent_category_raises(self, storage):
        with pytest.raises(ValueError, match="not found"):
            storage.delete_category("Nonexistent")


class TestIncomeTracking:
    def test_insert_income(self, storage):
        tx_id = storage.insert_transaction(
            source="manual",
            source_id="inc-1",
            amount=5000.0,
            merchant="Salary",
            category="Income",
            transaction_date="2026-04-01T09:00:00",
            tx_type="income",
        )
        tx = storage.get_transaction(tx_id)
        assert tx["type"] == "income"

    def test_get_spending_summary_excludes_income(self, storage):
        storage.insert_transaction(
            source="manual",
            source_id="exp-1",
            amount=50.0,
            merchant="Lunch",
            category="Food",
            transaction_date="2026-04-16T12:00:00",
        )
        storage.insert_transaction(
            source="manual",
            source_id="inc-1",
            amount=5000.0,
            merchant="Salary",
            category="Income",
            transaction_date="2026-04-16T09:00:00",
            tx_type="income",
        )
        summary = storage.get_spending_summary(
            start_date="2026-04-16", end_date="2026-04-16"
        )
        assert summary["total"] == 50.0

    def test_get_income_summary(self, storage):
        storage.insert_transaction(
            source="manual",
            source_id="inc-1",
            amount=5000.0,
            merchant="Salary",
            category="Salary",
            transaction_date="2026-04-01T09:00:00",
            tx_type="income",
        )
        storage.insert_transaction(
            source="manual",
            source_id="inc-2",
            amount=500.0,
            merchant="Freelance",
            category="Freelance",
            transaction_date="2026-04-15T10:00:00",
            tx_type="income",
        )
        summary = storage.get_income_summary(
            start_date="2026-04-01", end_date="2026-04-30"
        )
        assert summary["total"] == 5500.0
        assert summary["by_category"]["Salary"] == 5000.0
        assert summary["by_category"]["Freelance"] == 500.0

    def test_get_balance(self, storage):
        storage.insert_transaction(
            source="manual",
            source_id="exp-1",
            amount=100.0,
            merchant="Groceries",
            category="Food",
            transaction_date="2026-04-10T12:00:00",
        )
        storage.insert_transaction(
            source="manual",
            source_id="inc-1",
            amount=5000.0,
            merchant="Salary",
            category="Salary",
            transaction_date="2026-04-01T09:00:00",
            tx_type="income",
        )
        balance = storage.get_balance(
            start_date="2026-04-01", end_date="2026-04-30"
        )
        assert balance["income"] == 5000.0
        assert balance["expenses"] == 100.0
        assert balance["net"] == 4900.0


class TestMerchantOverrides:
    def test_set_and_get_override(self, storage):
        storage.set_merchant_override("BAN MIAN", "Food")
        overrides = storage.get_merchant_overrides()
        assert "BAN MIAN" in overrides
        assert overrides["BAN MIAN"] == "Food"

    def test_set_override_upserts(self, storage):
        storage.set_merchant_override("BAN MIAN", "Food")
        storage.set_merchant_override("BAN MIAN", "Transport")
        overrides = storage.get_merchant_overrides()
        assert overrides["BAN MIAN"] == "Transport"
        assert len(overrides) == 1

    def test_remove_override(self, storage):
        storage.set_merchant_override("BAN MIAN", "Food")
        storage.remove_merchant_override("BAN MIAN")
        overrides = storage.get_merchant_overrides()
        assert "BAN MIAN" not in overrides

    def test_get_overrides_empty(self, storage):
        overrides = storage.get_merchant_overrides()
        assert overrides == {}
