import pytest
import calendar
from datetime import datetime, timedelta, date
from src.storage import Storage


class TestBudgetCRUD:
    def test_create_overall_monthly_budget(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        budget_id = storage.create_budget(category=None, amount=3000.0, period="monthly")
        assert isinstance(budget_id, int)
        budgets = storage.get_budgets()
        assert len(budgets) == 1
        assert budgets[0]["category"] is None
        assert budgets[0]["amount"] == 3000.0
        assert budgets[0]["period"] == "monthly"

    def test_create_category_budget(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category="Dining", amount=200.0, period="monthly")
        budgets = storage.get_budgets()
        assert budgets[0]["category"] == "Dining"

    def test_create_weekly_budget(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category="Dining", amount=50.0, period="weekly")
        budgets = storage.get_budgets()
        assert budgets[0]["period"] == "weekly"

    def test_same_category_can_have_both_monthly_and_weekly(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category="Dining", amount=200.0, period="monthly")
        storage.create_budget(category="Dining", amount=50.0, period="weekly")
        assert len(storage.get_budgets()) == 2

    def test_duplicate_category_period_raises(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category="Dining", amount=200.0, period="monthly")
        with pytest.raises(ValueError, match="already exists"):
            storage.create_budget(category="Dining", amount=300.0, period="monthly")

    def test_update_budget_amount(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        budget_id = storage.create_budget(category=None, amount=3000.0, period="monthly")
        storage.update_budget(budget_id, amount=4000.0)
        assert storage.get_budgets()[0]["amount"] == 4000.0

    def test_update_nonexistent_raises(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        with pytest.raises(ValueError):
            storage.update_budget(999, amount=100.0)

    def test_delete_budget(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        budget_id = storage.create_budget(category=None, amount=3000.0, period="monthly")
        storage.delete_budget(budget_id)
        assert storage.get_budgets() == []

    def test_delete_nonexistent_raises(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        with pytest.raises(ValueError):
            storage.delete_budget(999)


class TestBudgetProgress:
    def test_empty_progress_when_no_budgets(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        assert storage.get_budget_progress() == []

    def test_monthly_budget_zero_spending(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category=None, amount=3000.0, period="monthly")
        progress = storage.get_budget_progress()
        assert len(progress) == 1
        p = progress[0]
        assert p["spent"] == 0.0
        assert p["remaining"] == 3000.0
        assert p["percent"] == 0.0
        assert p["status"] == "on_track"
        assert p["label"] == "Overall"
        assert p["budget_amount"] == 3000.0

    def test_category_budget_only_counts_matching_category(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category="Dining", amount=200.0, period="monthly")
        today = date.today().isoformat()
        in_memory_db.executemany(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, category, transaction_date, type) VALUES ('manual', ?, ?, 'SGD', 1.0, 'M', ?, ?, 'expense')",
            [("b1", 50.0, "Dining", today), ("b2", 100.0, "Transport", today)],
        )
        in_memory_db.commit()
        progress = storage.get_budget_progress()
        assert progress[0]["spent"] == 50.0  # only Dining

    def test_overall_budget_sums_all_expense_categories(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category=None, amount=1000.0, period="monthly")
        today = date.today().isoformat()
        in_memory_db.executemany(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, category, transaction_date, type) VALUES ('manual', ?, ?, 'SGD', 1.0, 'M', ?, ?, 'expense')",
            [("b1", 100.0, "Dining", today), ("b2", 50.0, "Transport", today)],
        )
        in_memory_db.commit()
        progress = storage.get_budget_progress()
        assert progress[0]["spent"] == 150.0

    def test_income_excluded_from_budget_progress(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category=None, amount=1000.0, period="monthly")
        today = date.today().isoformat()
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', 'i1', 5000, 'SGD', 1.0, 'Employer', ?, 'income')",
            (today,),
        )
        in_memory_db.commit()
        assert storage.get_budget_progress()[0]["spent"] == 0.0

    def test_previous_month_transactions_excluded(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category=None, amount=1000.0, period="monthly")
        last_month = (date.today().replace(day=1) - timedelta(days=1)).isoformat()
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', 'b1', 500.0, 'SGD', 1.0, 'M', ?, 'expense')",
            (last_month,),
        )
        in_memory_db.commit()
        assert storage.get_budget_progress()[0]["spent"] == 0.0

    def test_status_on_track_below_80(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category=None, amount=100.0, period="monthly")
        today = date.today().isoformat()
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', 'b1', 70.0, 'SGD', 1.0, 'M', ?, 'expense')",
            (today,),
        )
        in_memory_db.commit()
        assert storage.get_budget_progress()[0]["status"] == "on_track"

    def test_status_warning_at_80_percent(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category=None, amount=100.0, period="monthly")
        today = date.today().isoformat()
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', 'b1', 80.0, 'SGD', 1.0, 'M', ?, 'expense')",
            (today,),
        )
        in_memory_db.commit()
        assert storage.get_budget_progress()[0]["status"] == "warning"

    def test_status_over_budget_at_100_percent(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category=None, amount=100.0, period="monthly")
        today = date.today().isoformat()
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', 'b1', 110.0, 'SGD', 1.0, 'M', ?, 'expense')",
            (today,),
        )
        in_memory_db.commit()
        assert storage.get_budget_progress()[0]["status"] == "over_budget"

    def test_exchange_rate_applied_to_progress(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.create_budget(category=None, amount=200.0, period="monthly")
        today = date.today().isoformat()
        # JPY transaction: 1000 JPY at 0.01 rate = SGD 10
        in_memory_db.execute(
            "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, "
            "merchant, transaction_date, type) VALUES ('manual', 'b1', 1000.0, 'JPY', 0.01, 'M', ?, 'expense')",
            (today,),
        )
        in_memory_db.commit()
        assert storage.get_budget_progress()[0]["spent"] == pytest.approx(10.0, 0.01)
