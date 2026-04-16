import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.telegram_bot import TelegramBotService
from src.storage import Storage


@pytest.fixture
def bot_service(in_memory_db):
    storage = Storage(connection=in_memory_db)
    return TelegramBotService(storage=storage, bot_token="test-token")


class TestParseAddCommand:
    def test_parse_add_full(self, bot_service):
        result = bot_service.parse_add_command("12.50 Toast Box food 2026-04-16")
        assert result["amount"] == 12.50
        assert result["merchant"] == "Toast Box"
        assert result["category"] == "food"
        assert result["date"] == "2026-04-16"

    def test_parse_add_minimal(self, bot_service):
        result = bot_service.parse_add_command("5.00 Coffee Shop")
        assert result["amount"] == 5.00
        assert result["merchant"] == "Coffee Shop"
        assert result["category"] is None
        assert result["date"] is None

    def test_parse_add_invalid_amount(self, bot_service):
        result = bot_service.parse_add_command("abc Test")
        assert result is None


class TestFormatSummary:
    def test_format_daily_summary(self, bot_service, in_memory_db):
        in_memory_db.execute(
            """INSERT INTO transactions (source, source_id, amount, merchant, category, transaction_date)
               VALUES ('manual', 'm1', 12.50, 'Toast Box', 'Food', '2026-04-16T12:00:00')"""
        )
        in_memory_db.execute(
            """INSERT INTO transactions (source, source_id, amount, merchant, category, transaction_date)
               VALUES ('manual', 'm2', 25.00, 'Grab', 'Transport', '2026-04-16T13:00:00')"""
        )
        in_memory_db.commit()

        summary = bot_service.format_daily_summary("2026-04-16")
        assert "37.50" in summary
        assert "Food" in summary
        assert "Transport" in summary
