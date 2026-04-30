import pytest
from unittest.mock import MagicMock

from src.ingestion import IngestionPipeline
from src.parsers.base import ParseResult
from src.storage import Storage


@pytest.fixture
def storage(in_memory_db):
    return Storage(connection=in_memory_db)


def _result(**kwargs):
    defaults = dict(
        source="apple_wallet",
        source_id="aw-test-001",
        amount=12.50,
        merchant="Starbucks",
        currency="SGD",
        transaction_date="2026-04-15T09:00:00",
    )
    defaults.update(kwargs)
    return ParseResult(**defaults)


class TestIngestionPipelineIngest:
    def test_returns_dict_on_success(self, storage):
        pipeline = IngestionPipeline(storage)
        result = pipeline.ingest(_result())
        assert isinstance(result, dict)
        assert result["merchant"] == "Starbucks"
        assert result["amount"] == 12.50

    def test_returns_none_for_same_source_duplicate(self, storage):
        pipeline = IngestionPipeline(storage)
        pipeline.ingest(_result())
        # Second call with identical source_id
        result = pipeline.ingest(_result())
        assert result is None

    def test_returns_none_for_cross_source_duplicate(self, storage):
        pipeline = IngestionPipeline(storage)
        # First: apple_wallet
        pipeline.ingest(_result(source="apple_wallet", source_id="aw-1"))
        # Second: same merchant/amount, different source within 10 min
        result = pipeline.ingest(_result(source="dbs_paylah", source_id="dbs-1"))
        assert result is None

    def test_categorizer_is_applied(self, storage):
        categorizer = MagicMock()
        categorizer.categorize.return_value = ("Food", "keyword:coffee")
        categorizer.reload_overrides.return_value = None
        pipeline = IngestionPipeline(storage, categorizer=categorizer)
        result = pipeline.ingest(_result())
        assert result["category"] == "Food"

    def test_exchange_rate_is_applied(self, storage):
        exchange_service = MagicMock()
        exchange_service.get_rate.return_value = 3.5
        pipeline = IngestionPipeline(storage, exchange_service=exchange_service)
        result = pipeline.ingest(_result(currency="PLN"))
        assert result["exchange_rate"] == 3.5

    def test_recurring_detector_is_called(self, storage):
        detector = MagicMock()
        pipeline = IngestionPipeline(storage, detector=detector)
        pipeline.ingest(_result())
        detector.run.assert_called_once()
