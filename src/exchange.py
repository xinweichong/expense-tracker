import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CURRENCY_CODES = {
    "USD", "EUR", "GBP", "JPY", "THB", "MYR", "IDR", "PHP",
    "VND", "CNY", "HKD", "TWD", "KRW", "AUD", "NZD", "CAD",
    "CHF", "INR", "SGD",
}

FALLBACK_RATES = {
    "SGD": 1.0, "USD": 1.34, "EUR": 1.45, "GBP": 1.70,
    "JPY": 0.0091, "THB": 0.037, "MYR": 0.30, "IDR": 0.000082,
    "PHP": 0.023, "CNY": 0.18, "HKD": 0.17, "AUD": 0.87,
}


class ExchangeRateService:
    def __init__(self, api_url: Optional[str] = None, cache_hours: int = 24):
        self.api_url = api_url or os.environ.get(
            "EXCHANGE_RATE_API_URL", "https://open.er-api.com/v6/latest/SGD"
        )
        self.cache_hours = cache_hours
        self._rates: dict[str, float] = {}
        self._rates_fetched_at: Optional[datetime] = None

    def _is_cache_stale(self) -> bool:
        if not self._rates_fetched_at:
            return True
        return datetime.now() - self._rates_fetched_at > timedelta(hours=self.cache_hours)

    def _fetch_rates(self) -> dict[str, float]:
        try:
            resp = httpx.get(self.api_url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            rates = data.get("rates", {})
            self._rates = rates
            self._rates_fetched_at = datetime.now()
            logger.info("Fetched exchange rates: %d currencies", len(rates))
            return rates
        except Exception as e:
            logger.warning("Failed to fetch exchange rates: %s. Using fallback.", e)
            return FALLBACK_RATES

    def get_rate(self, currency: str) -> float:
        if currency == "SGD":
            return 1.0
        if self._is_cache_stale():
            self._fetch_rates()
        rate = self._rates.get(currency)
        if rate is None:
            logger.warning("No rate for %s, using fallback", currency)
            return FALLBACK_RATES.get(currency, 1.0)
        return rate

    def parse_currency_amount(self, text: str) -> tuple[float, str]:
        parts = text.strip().split()
        try:
            amount = float(parts[0])
        except (ValueError, IndexError):
            return (0.0, "SGD")
        if len(parts) >= 2 and parts[1].upper() in CURRENCY_CODES:
            return (amount, parts[1].upper())
        return (amount, "SGD")
