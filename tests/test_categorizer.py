import pytest
from src.categorizer import Categorizer


@pytest.fixture
def categorizer():
    categories = [
        {"name": "Food", "keywords": ["restaurant", "cafe", "food", "kopitiam", "toast box", "ya kun"], "icon": "🍜"},
        {"name": "Transport", "keywords": ["grab", "gojek", "comfortdelgro", "mrt", "bus", "taxi", "cdg"], "icon": "🚗"},
        {"name": "Shopping", "keywords": ["shopee", "lazada", "fairprice", "cold storage", "ntuc"], "icon": "🛒"},
        {"name": "Other", "keywords": [], "icon": "📌"},
    ]
    return Categorizer(categories)


class TestCategorizer:
    def test_match_exact_keyword(self, categorizer):
        assert categorizer.categorize("Toast Box Jurong") == "Food"

    def test_match_case_insensitive(self, categorizer):
        assert categorizer.categorize("GRAB RIDE") == "Transport"

    def test_match_partial_merchant(self, categorizer):
        assert categorizer.categorize("FairPrice Finest") == "Shopping"

    def test_no_match_returns_other(self, categorizer):
        assert categorizer.categorize("Unknown Merchant XYZ") == "Other"

    def test_empty_merchant_returns_other(self, categorizer):
        assert categorizer.categorize("") == "Other"

    def test_first_match_wins(self, categorizer):
        assert categorizer.categorize("food court") == "Food"
