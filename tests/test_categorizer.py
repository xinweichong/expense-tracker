import pytest
from src.categorizer import Categorizer
from src.storage import Storage


@pytest.fixture
def categories():
    return [
        {"name": "Food", "keywords": ["restaurant", "cafe", "food", "kopitiam", "toast box", "ya kun"], "icon": "🍜"},
        {"name": "Transport", "keywords": ["grab", "gojek", "comfortdelgro", "mrt", "bus", "taxi", "cdg"], "icon": "🚗"},
        {"name": "Shopping", "keywords": ["shopee", "lazada", "fairprice", "cold storage", "ntuc"], "icon": "🛒"},
        {"name": "Other", "keywords": [], "icon": "📌"},
    ]


class TestCategorizerBasic:
    def test_keyword_match(self, categories):
        c = Categorizer(categories)
        category, source = c.categorize("Toast Box Jurong")
        assert category == "Food"
        assert source == "keyword:toast box"

    def test_no_match_default(self, categories):
        c = Categorizer(categories)
        category, source = c.categorize("Unknown Merchant XYZ")
        assert category == "Other"
        assert source == "default"

    def test_empty_merchant(self, categories):
        c = Categorizer(categories)
        category, source = c.categorize("")
        assert category == "Other"
        assert source == "default"

    def test_case_insensitive(self, categories):
        c = Categorizer(categories)
        category, source = c.categorize("GRAB RIDE")
        assert category == "Transport"
        assert source == "keyword:grab"


class TestCategorizerOverrides:
    def test_override_priority(self, categories):
        c = Categorizer(categories, overrides={"toast box": "Transport"})
        category, source = c.categorize("Toast Box")
        assert category == "Transport"
        assert source == "learned"

    def test_case_insensitive_override(self, categories):
        c = Categorizer(categories, overrides={"GRAB": "Food"})
        category, source = c.categorize("grab ride")
        assert category == "Food"
        assert source == "learned"

    def test_keyword_when_no_override(self, categories):
        c = Categorizer(categories, overrides={})
        category, source = c.categorize("Toast Box")
        assert category == "Food"
        assert "keyword" in source

    def test_reload_overrides(self, categories):
        c = Categorizer(categories, overrides={})
        category, _ = c.categorize("Toast Box")
        assert category == "Food"
        c.reload_overrides({"toast box": "Transport"})
        category, source = c.categorize("Toast Box")
        assert category == "Transport"
        assert source == "learned"

    def test_override_beats_keyword(self, categories):
        c = Categorizer(categories, overrides={"fairprice": "Food"})
        category, source = c.categorize("FairPrice Finest")
        assert category == "Food"
        assert source == "learned"


# ── Task 5: Categorizer.learn_merchant ───────────────────────────────────────

class TestLearnMerchant:
    def test_learn_merchant_persists_to_storage(self, categories, in_memory_db):
        storage = Storage(connection=in_memory_db)
        c = Categorizer(categories)
        c.learn_merchant("Grab", "Transport", storage)
        overrides = storage.get_merchant_overrides()
        assert "grab" in {k.lower() for k in overrides}

    def test_learn_merchant_updates_in_memory_overrides(self, categories, in_memory_db):
        storage = Storage(connection=in_memory_db)
        c = Categorizer(categories)
        c.learn_merchant("Netflix", "Entertainment", storage)
        category, source = c.categorize("Netflix")
        assert category == "Entertainment"
        assert source == "learned"

    def test_learn_merchant_with_none_storage_does_not_raise(self, categories):
        c = Categorizer(categories)
        # Should silently skip persistence when no storage provided
        c.learn_merchant("Grab", "Transport", None)
        # In-memory override should still be updated
        category, _ = c.categorize("Grab")
        assert category == "Transport"
