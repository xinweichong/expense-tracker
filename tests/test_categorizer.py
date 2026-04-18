import pytest
from src.categorizer import Categorizer


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
