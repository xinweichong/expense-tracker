import pytest
from src.storage import Storage


def _insert_tx(db, source_id, amount, category, tx_type="expense", exchange_rate=1.0, merchant="TestMerchant", date="2026-04-15"):
    db.execute(
        """INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, merchant, category, transaction_date, type)
           VALUES ('test', ?, ?, 'SGD', ?, ?, ?, ?, ?)""",
        (source_id, amount, exchange_rate, merchant, category, date, tx_type),
    )
    db.commit()


def _seed_categories(db):
    """Insert categories with known types."""
    db.execute("INSERT OR IGNORE INTO categories (name, type) VALUES ('Dining', 'wants')")
    db.execute("INSERT OR IGNORE INTO categories (name, type) VALUES ('Transport', 'needs')")
    db.execute("INSERT OR IGNORE INTO categories (name, type) VALUES ('Groceries', 'needs')")
    db.execute("INSERT OR IGNORE INTO categories (name, type) VALUES ('Other', 'neutral')")
    db.commit()


class TestHealthScoreNoIncome:
    def test_returns_no_income_flag_when_no_income(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "tx1", 100.0, "Dining", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["has_income_data"] is False
        assert result["score"] is None
        assert result["grade"] is None

    def test_returns_has_income_when_income_present(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 5000.0, "Income", tx_type="income")
        result = storage.get_health_score(months=1)
        assert result["has_income_data"] is True
        assert result["score"] is not None


class TestHealthScoreSavingsRate:
    def test_perfect_savings_rate_gives_40_pts(self, in_memory_db):
        """Income=1000, expense=0 → savings_rate=1.0, score = min(1/0.2,1)*40 = 40"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        result = storage.get_health_score(months=1)
        assert result["components"]["savings_rate"]["score"] == pytest.approx(40.0, abs=0.1)

    def test_benchmark_savings_rate_gives_40_pts(self, in_memory_db):
        """Income=1000, expense=800 → savings=200, rate=0.20 → score=40"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 800.0, "Dining", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["components"]["savings_rate"]["score"] == pytest.approx(40.0, abs=0.1)

    def test_half_benchmark_savings_rate_gives_20_pts(self, in_memory_db):
        """Income=1000, expense=900 → savings=100, rate=0.10 → score = (0.10/0.20)*40 = 20"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 900.0, "Dining", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["components"]["savings_rate"]["score"] == pytest.approx(20.0, abs=0.1)

    def test_negative_savings_gives_0_pts(self, in_memory_db):
        """Income=1000, expense=1200 → savings=-200, rate=-0.20 → score=0"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 1200.0, "Dining", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["components"]["savings_rate"]["score"] == pytest.approx(0.0, abs=0.1)


class TestHealthScoreNeedsWantsRatio:
    def test_needs_below_benchmark_gives_full_20_pts(self, in_memory_db):
        """Income=1000, needs=400 (40% < 50%) → needs_score = 20"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 400.0, "Transport", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["components"]["needs_ratio"]["score"] == pytest.approx(20.0, abs=0.1)

    def test_needs_at_benchmark_gives_full_20_pts(self, in_memory_db):
        """Income=1000, needs=500 (50% = benchmark) → needs_score = 20"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 500.0, "Transport", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["components"]["needs_ratio"]["score"] == pytest.approx(20.0, abs=0.1)

    def test_needs_above_benchmark_reduces_score(self, in_memory_db):
        """Income=1000, needs=750 (75% → 25pp over 50%) → score = (1 - 25/50)*20 = 10"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 750.0, "Transport", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["components"]["needs_ratio"]["score"] == pytest.approx(10.0, abs=0.1)

    def test_wants_below_benchmark_gives_full_20_pts(self, in_memory_db):
        """Income=1000, wants=200 (20% < 30%) → wants_score = 20"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 200.0, "Dining", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["components"]["wants_ratio"]["score"] == pytest.approx(20.0, abs=0.1)

    def test_wants_double_benchmark_gives_0_pts(self, in_memory_db):
        """Income=1000, wants=600 (60% → 30pp over 30%) → score = (1 - 30/30)*20 = 0"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 600.0, "Dining", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["components"]["wants_ratio"]["score"] == pytest.approx(0.0, abs=0.1)


class TestHealthScoreAnomalyFrequency:
    def test_zero_anomalies_gives_10_pts(self, in_memory_db):
        """All transactions near merchant average → anomaly_score = 10"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        in_memory_db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('anomaly_multiplier', '2.0')")
        in_memory_db.commit()
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        for i in range(5):
            _insert_tx(in_memory_db, f"e{i}", 50.0, "Dining", merchant="RestaurantA")
        result = storage.get_health_score(months=1)
        assert result["components"]["anomaly_frequency"]["score"] == pytest.approx(10.0, abs=0.1)
        assert result["components"]["anomaly_frequency"]["value"] == 0

    def test_5_anomalies_gives_0_pts(self, in_memory_db):
        """5+ anomalies → score = max(0, 1 - 5/5)*10 = 0"""
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        in_memory_db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('anomaly_multiplier', '2.0')")
        in_memory_db.commit()
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        # Insert 10 historical transactions with low avg amount
        for i in range(10):
            in_memory_db.execute(
                "INSERT INTO transactions (source, source_id, amount, currency, exchange_rate, merchant, category, transaction_date, type) "
                "VALUES ('test', ?, 10.0, 'SGD', 1.0, 'RestaurantA', 'Dining', '2025-01-15', 'expense')",
                (f"hist{i}",),
            )
        in_memory_db.commit()
        # 5 anomalous transactions (100 >> 2*10 = 20 threshold)
        for i in range(5):
            _insert_tx(in_memory_db, f"anom{i}", 100.0, "Dining", merchant="RestaurantA")
        result = storage.get_health_score(months=1)
        assert result["components"]["anomaly_frequency"]["score"] == pytest.approx(0.0, abs=0.1)
        assert result["components"]["anomaly_frequency"]["value"] == 5


class TestHealthScoreTotal:
    def test_score_sums_components(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        in_memory_db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('anomaly_multiplier', '2.0')")
        in_memory_db.commit()
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 200.0, "Transport", tx_type="expense")  # needs
        _insert_tx(in_memory_db, "exp2", 100.0, "Dining", tx_type="expense")    # wants
        result = storage.get_health_score(months=1)
        components = result["components"]
        expected_total = round(
            components["savings_rate"]["score"]
            + components["needs_ratio"]["score"]
            + components["wants_ratio"]["score"]
            + components["budget_adherence"]["score"]
            + components["anomaly_frequency"]["score"]
        )
        assert result["score"] == expected_total

    def test_grade_excellent(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        in_memory_db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('anomaly_multiplier', '2.0')")
        in_memory_db.commit()
        # Max score: save everything, zero needs/wants
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        result = storage.get_health_score(months=1)
        # savings=40, needs=20, wants=20, budget=0 (no budgets), anomaly=10 → 90
        assert result["grade"] == "Excellent"
        assert result["score"] >= 80

    def test_grade_needs_attention(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        _seed_categories(in_memory_db)
        in_memory_db.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES ('anomaly_multiplier', '2.0')")
        in_memory_db.commit()
        # Over budget on everything: income=1000, expense=1100 → savings=-100→0pts; needs=800→0pts; wants=800→0pts
        _insert_tx(in_memory_db, "inc1", 1000.0, "Income", tx_type="income")
        _insert_tx(in_memory_db, "exp1", 800.0, "Transport", tx_type="expense")
        _insert_tx(in_memory_db, "exp2", 800.0, "Dining", tx_type="expense")
        result = storage.get_health_score(months=1)
        assert result["grade"] == "Needs Attention"
        assert result["score"] < 40


class TestCategoryTypeExtension:
    def test_add_category_with_type(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.add_category("Rent", "rent,landlord", icon="🏠", cat_type="needs")
        cats = storage.get_categories()
        rent = next(c for c in cats if c["name"] == "Rent")
        assert rent["type"] == "needs"

    def test_add_category_defaults_to_neutral(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.add_category("Misc", "misc", icon="📌")
        cats = storage.get_categories()
        misc = next(c for c in cats if c["name"] == "Misc")
        assert misc["type"] == "neutral"

    def test_update_category_type(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.add_category("Gaming", "steam,epic", icon="🎮")
        storage.update_category("Gaming", cat_type="wants")
        cats = storage.get_categories()
        gaming = next(c for c in cats if c["name"] == "Gaming")
        assert gaming["type"] == "wants"

    def test_invalid_type_raises(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        storage.add_category("X", "", icon="📌")
        with pytest.raises(ValueError):
            storage.update_category("X", cat_type="invalid_type")
