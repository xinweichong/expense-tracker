import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.telegram_bot import TelegramBotService, estimate_next_date
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


class TestEstimateNextDate:
    def test_weekly(self):
        result = estimate_next_date("weekly", "2026-04-01")
        assert result == "08 Apr"

    def test_biweekly(self):
        result = estimate_next_date("biweekly", "2026-04-01")
        assert result == "15 Apr"

    def test_monthly(self):
        result = estimate_next_date("monthly", "2026-03-15")
        assert result == "15 Apr"

    def test_monthly_december_rollover(self):
        result = estimate_next_date("monthly", "2026-12-10")
        assert result == "10 Jan"


class TestInsightsCommand:
    @pytest.mark.asyncio
    async def test_insights_sends_message(self, bot_service):
        bot_service.storage.get_spending_summary = MagicMock(return_value={
            "total": 150.0,
            "by_category": {"Food": 80.0, "Transport": 70.0},
        })
        bot_service.storage.get_merchant_ranking = MagicMock(return_value=[
            {"merchant": "Toast Box", "total": 50.0, "visits": 3},
            {"merchant": "Grab", "total": 40.0, "visits": 2},
        ])
        bot_service.storage.get_average_daily = MagicMock(return_value=5.0)

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot_service._insights(update, context)

        update.message.reply_text.assert_called_once()
        call_kwargs = update.message.reply_text.call_args
        text = call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1].get("text", "")
        assert "Food" in text
        assert "80.00" in text
        assert "5.00" in text
        assert "Toast Box" in text


class TestSubscriptionsCommand:
    @pytest.mark.asyncio
    async def test_subscriptions_weekly_formatting(self, bot_service, in_memory_db):
        in_memory_db.execute(
            """INSERT INTO recurring_transactions (merchant, avg_amount, frequency, category, first_seen, last_seen, occurrences)
               VALUES ('Netflix', 15.98, 'weekly', 'Entertainment', '2026-01-01', '2026-04-15', 16)"""
        )
        in_memory_db.commit()

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot_service._subscriptions(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "Netflix" in text
        assert "weekly" in text
        assert "22 Apr" in text  # 2026-04-15 + 7 days
        # 15.98 * 4.33 ≈ 69.19
        assert "69.1" in text


class TestBalanceCommand:
    @pytest.mark.asyncio
    async def test_balance_includes_month_and_amounts(self, bot_service):
        bot_service.storage.get_balance = MagicMock(return_value={
            "income": 5000.0,
            "expenses": 1200.0,
            "net": 3800.0,
        })

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot_service._balance(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "5000.00" in text
        assert "1200.00" in text
        assert "3800.00" in text
        assert "days remaining" in text
        # Month name should appear (e.g. "April 2026")
        from datetime import datetime
        month_str = datetime.now().strftime("%B %Y")
        assert month_str in text

    @pytest.mark.asyncio
    async def test_balance_empty_no_keyboard(self, bot_service):
        bot_service.storage.get_balance = MagicMock(return_value={
            "income": 0.0, "expenses": 0.0, "net": 0.0,
        })

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        context = MagicMock()

        await bot_service._balance(update, context)

        update.message.reply_text.assert_called_once_with("No transactions this month")

