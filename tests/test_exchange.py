import pytest
from datetime import datetime

from src.config import local_now
from src.exchange import ExchangeRateService, FALLBACK_RATES


class TestExchangeRateService:
    def test_get_rate_sgd_returns_1(self):
        svc = ExchangeRateService()
        assert svc.get_rate("SGD") == 1.0

    def test_parse_currency_detects_thb(self):
        svc = ExchangeRateService()
        amount, currency = svc.parse_currency_amount("500 THB")
        assert amount == 500.0
        assert currency == "THB"

    def test_parse_currency_no_currency_returns_sgd(self):
        svc = ExchangeRateService()
        amount, currency = svc.parse_currency_amount("12.50")
        assert amount == 12.50
        assert currency == "SGD"

    def test_parse_currency_jpy(self):
        svc = ExchangeRateService()
        amount, currency = svc.parse_currency_amount("2000 JPY")
        assert amount == 2000.0
        assert currency == "JPY"

    def test_fallback_rate_used_when_no_fetch(self):
        svc = ExchangeRateService()
        svc._rates = {}  # Empty cache, no fetch
        svc._rates_fetched_at = local_now()  # Not stale
        rate = svc.get_rate("THB")
        assert rate == FALLBACK_RATES["THB"]

    def test_parse_currency_invalid_amount(self):
        svc = ExchangeRateService()
        amount, currency = svc.parse_currency_amount("abc")
        assert amount == 0.0
        assert currency == "SGD"

    def test_parse_currency_usd(self):
        svc = ExchangeRateService()
        amount, currency = svc.parse_currency_amount("100 USD")
        assert amount == 100.0
        assert currency == "USD"

    def test_parse_currency_case_insensitive(self):
        svc = ExchangeRateService()
        amount, currency = svc.parse_currency_amount("500 thb")
        assert amount == 500.0
        assert currency == "THB"

    def test_parse_currency_unknown_code_defaults_sgd(self):
        svc = ExchangeRateService()
        amount, currency = svc.parse_currency_amount("500 XYZ")
        assert amount == 500.0
        assert currency == "SGD"

    def test_get_rate_unknown_currency_uses_fallback(self):
        svc = ExchangeRateService()
        svc._rates = {}
        svc._rates_fetched_at = local_now()
        rate = svc.get_rate("USD")
        assert rate == FALLBACK_RATES["USD"]

    def test_cache_stale_when_no_fetch_time(self):
        svc = ExchangeRateService()
        assert svc._is_cache_stale() is True

    def test_cache_not_stale_after_set(self):
        svc = ExchangeRateService()
        svc._rates_fetched_at = local_now()
        assert svc._is_cache_stale() is False

    def test_get_rate_triggers_fetch_when_stale(self):
        svc = ExchangeRateService()
        fetched = []

        def mock_fetch():
            fetched.append(True)
            svc._rates = FALLBACK_RATES
            svc._rates_fetched_at = local_now()
            return FALLBACK_RATES

        svc._fetch_rates = mock_fetch
        svc.get_rate("USD")
        assert len(fetched) == 1
