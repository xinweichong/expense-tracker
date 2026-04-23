import pytest
from datetime import datetime
from src.storage import Storage


class TestMerchantList:
    def test_empty_list_when_no_transactions(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        result = storage.get_merchant_list()
        assert result == []

    def test_basic_stats_computed_from_transactions(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        today = datetime.now().strftime("%Y-%m-%d")
        in_memory_db.executemany(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, category, transaction_date, type) VALUES ('manual', ?, ?, 'SGD', 1.0, 'Grab', "
            "'Transport', ?, 'expense')",
            [("g1", 12.0, today), ("g2", 18.0, today), ("g3", 10.0, today)],
        )
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, category, transaction_date, type) VALUES ('manual', 's1', 5.0, 'SGD', 1.0, "
            "'Starbucks', 'Dining', ?, 'expense')",
            (today,),
        )
        in_memory_db.commit()
        result = storage.get_merchant_list()
        assert len(result) == 2
        grab = next(r for r in result if r["merchant"] == "Grab")
        assert grab["transaction_count"] == 3
        assert grab["total_sgd"] == 40.0
        assert grab["avg_amount_sgd"] == pytest.approx(40.0 / 3, 0.01)
        assert grab["category"] == "Transport"
        assert grab["first_seen"] == today
        assert grab["last_seen"] == today
        assert grab["tags"] == []
        assert grab["notes"] == ""

    def test_sorted_by_total_spent_by_default(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        today = datetime.now().strftime("%Y-%m-%d")
        in_memory_db.executemany(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', ?, ?, 'SGD', 1.0, ?, ?, 'expense')",
            [("a1", 100.0, "Alpha", today), ("b1", 50.0, "Beta", today)],
        )
        in_memory_db.commit()
        result = storage.get_merchant_list()
        assert result[0]["merchant"] == "Alpha"
        assert result[1]["merchant"] == "Beta"

    def test_sorted_by_transaction_count(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        today = datetime.now().strftime("%Y-%m-%d")
        in_memory_db.executemany(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', ?, 1.0, 'SGD', 1.0, ?, ?, 'expense')",
            [("a1", "Alpha", today), ("b1", "Beta", today), ("b2", "Beta", today)],
        )
        in_memory_db.commit()
        result = storage.get_merchant_list(sort_by="transaction_count")
        assert result[0]["merchant"] == "Beta"

    def test_name_search_filter(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        today = datetime.now().strftime("%Y-%m-%d")
        in_memory_db.executemany(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', ?, 10.0, 'SGD', 1.0, ?, ?, 'expense')",
            [("g1", "Grab", today), ("s1", "Starbucks", today)],
        )
        in_memory_db.commit()
        result = storage.get_merchant_list(name_search="grab")
        assert len(result) == 1
        assert result[0]["merchant"] == "Grab"

    def test_income_transactions_excluded(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        today = datetime.now().strftime("%Y-%m-%d")
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, merchant, transaction_date, type) "
            "VALUES ('manual', 'i1', 5000, 'Employer', ?, 'income')",
            (today,),
        )
        in_memory_db.commit()
        result = storage.get_merchant_list()
        assert result == []

    def test_pagination(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        today = datetime.now().strftime("%Y-%m-%d")
        for i in range(5):
            in_memory_db.execute(
                "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
                "merchant, transaction_date, type) VALUES ('manual', ?, ?, 'SGD', 1.0, ?, ?, 'expense')",
                (f"s{i}", float(100 - i * 10), f"Merchant{i}", today),
            )
        in_memory_db.commit()
        page1 = storage.get_merchant_list(limit=3, offset=0)
        page2 = storage.get_merchant_list(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2


class TestMerchantTags:
    def test_get_tags_returns_empty_for_unknown_merchant(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        result = storage.get_merchant_tags("Unknown")
        assert result == {"merchant": "Unknown", "tags": [], "notes": ""}

    def test_set_and_get_tags(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.set_merchant_tags("Grab", ["online", "local"])
        result = storage.get_merchant_tags("Grab")
        assert result["tags"] == ["online", "local"]
        assert result["notes"] == ""

    def test_set_notes(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.set_merchant_notes("Starbucks", "Near office")
        result = storage.get_merchant_tags("Starbucks")
        assert result["notes"] == "Near office"
        assert result["tags"] == []

    def test_set_tags_overwrites_previous(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.set_merchant_tags("Grab", ["online"])
        storage.set_merchant_tags("Grab", ["online", "local"])
        result = storage.get_merchant_tags("Grab")
        assert result["tags"] == ["online", "local"]

    def test_set_tags_and_notes_independently(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.set_merchant_tags("Grab", ["online"])
        storage.set_merchant_notes("Grab", "My app")
        result = storage.get_merchant_tags("Grab")
        assert result["tags"] == ["online"]
        assert result["notes"] == "My app"


class TestMerchantProfile:
    def test_profile_includes_stats_and_tags(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        today = datetime.now().strftime("%Y-%m-%d")
        in_memory_db.executemany(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, category, transaction_date, type) VALUES ('manual', ?, ?, 'SGD', 1.0, "
            "'Grab', 'Transport', ?, 'expense')",
            [("g1", 10.0, today), ("g2", 20.0, today)],
        )
        in_memory_db.commit()
        storage.set_merchant_tags("Grab", ["online", "local"])
        storage.set_merchant_notes("Grab", "Ride-hailing")
        profile = storage.get_merchant_profile("Grab")
        assert profile["merchant"] == "Grab"
        assert profile["total_sgd"] == 30.0
        assert profile["transaction_count"] == 2
        assert profile["tags"] == ["online", "local"]
        assert profile["notes"] == "Ride-hailing"

    def test_profile_returns_none_for_unknown(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        assert storage.get_merchant_profile("NonExistent") is None
