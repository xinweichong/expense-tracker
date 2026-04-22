import pytest
import pytest_asyncio
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport
from src.webhook import create_webhook_app
from src.storage import Storage


@pytest.fixture
def webhook_app(in_memory_db):
    storage = Storage(connection=in_memory_db)
    return create_webhook_app(storage)


@pytest_asyncio.fixture
async def client(webhook_app):
    transport = ASGITransport(app=webhook_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAppleWalletWebhook:
    @pytest.mark.asyncio
    async def test_valid_payload_returns_200(self, client, in_memory_db):
        response = await client.post("/webhook/apple-wallet", json={
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card": "DBS Debit Mastercard",
            "date": "16/04/2026 12:30:00",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "transaction_id" in data

    @pytest.mark.asyncio
    async def test_foreign_currency_payload(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        mock_exchange = MagicMock()
        mock_exchange.get_rate.return_value = 0.35  # 1 PLN = 0.35 SGD (example)
        app = create_webhook_app(storage, exchange_service=mock_exchange)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/webhook/apple-wallet", json={
                "amount": "PLN 3.78",
                "merchant": "Zabka",
                "card": "Visa Signature",
                "date": "16/04/2026 12:30:00",
            })
        assert response.status_code == 200
        tx_id = response.json()["transaction_id"]
        tx = storage.get_transaction(tx_id)
        assert tx["currency"] == "PLN"
        assert tx["amount"] == pytest.approx(3.78)
        assert tx["exchange_rate"] == pytest.approx(0.35)
        mock_exchange.get_rate.assert_called_once_with("PLN")

    @pytest.mark.asyncio
    async def test_sgd_payload_skips_exchange_lookup(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        mock_exchange = MagicMock()
        app = create_webhook_app(storage, exchange_service=mock_exchange)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post("/webhook/apple-wallet", json={
                "amount": "12.50",
                "merchant": "Toast Box",
                "card": "DBS Debit",
                "date": "16/04/2026 12:30:00",
            })
        # SGD transactions should NOT trigger a rate lookup
        mock_exchange.get_rate.assert_not_called()

    @pytest.mark.asyncio
    async def test_categorizer_is_called(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        mock_cat = MagicMock()
        mock_cat.categorize.return_value = ("Food & Drink", "keyword:toast")
        app = create_webhook_app(storage, categorizer=mock_cat)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/webhook/apple-wallet", json={
                "amount": "-12.50",
                "merchant": "Toast Box",
                "card": "DBS Debit",
                "date": "16/04/2026 12:30:00",
            })
        assert response.status_code == 200
        tx_id = response.json()["transaction_id"]
        tx = storage.get_transaction(tx_id)
        assert tx["category"] == "Food & Drink"
        mock_cat.categorize.assert_called_once_with("Toast Box")

    @pytest.mark.asyncio
    async def test_on_transaction_callback_fires(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        callback = MagicMock()
        app = create_webhook_app(storage, on_transaction=callback)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/webhook/apple-wallet", json={
                "amount": "-12.50",
                "merchant": "Toast Box",
                "card": "DBS Debit",
                "date": "16/04/2026 12:30:00",
            })
        assert response.status_code == 200
        tx_id = response.json()["transaction_id"]
        callback.assert_called_once_with(tx_id, pytest.approx(12.50), "Toast Box", None, "default", "apple_wallet")

    @pytest.mark.asyncio
    async def test_card_name_stored_in_description(self, client, in_memory_db):
        storage = Storage(connection=in_memory_db)
        response = await client.post("/webhook/apple-wallet", json={
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card": "Visa Signature",
            "date": "16/04/2026 12:30:00",
        })
        tx_id = response.json()["transaction_id"]
        tx = storage.get_transaction(tx_id)
        assert tx["description"] == "Apple Wallet - Visa Signature"

    @pytest.mark.asyncio
    async def test_numeric_amount_accepted(self, client):
        """Numeric JSON amount values are coerced to string and parsed."""
        response = await client.post("/webhook/apple-wallet", json={
            "amount": 12.50,
            "merchant": "Toast Box",
            "card": "DBS Debit",
            "date": "16/04/2026 12:30:00",
        })
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_amount_returns_400(self, client):
        response = await client.post("/webhook/apple-wallet", json={
            "merchant": "Test",
            "card": "Visa",
            "date": "16/04/2026 12:00:00",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_merchant_returns_400(self, client):
        response = await client.post("/webhook/apple-wallet", json={
            "amount": "-10.0",
            "card": "Visa",
            "date": "16/04/2026 12:00:00",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_within_window_returns_200(self, client, in_memory_db):
        payload = {
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card": "DBS Debit",
            "date": "16/04/2026 12:30:00",
        }
        r1 = await client.post("/webhook/apple-wallet", json=payload)
        assert r1.status_code == 200
        r2 = await client.post("/webhook/apple-wallet", json=payload)
        assert r2.status_code == 200
        assert r2.json()["status"] == "duplicate"


class TestWebhookDedup:
    @pytest.mark.asyncio
    async def test_cross_source_duplicate_detected(self, in_memory_db):
        storage = Storage(connection=in_memory_db)
        # Simulate a DBS PayLah! transaction already in the DB
        storage.insert_transaction(
            source="dbs_paylah",
            source_id="email-123",
            amount=8.20,
            merchant="BAN MIAN",
            transaction_date="2026-04-16T12:00:00",
        )
        app = create_webhook_app(storage)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/webhook/apple-wallet", json={
                "amount": "-8.20",
                "merchant": "BAN MIAN",
                "card": "DBS Debit",
                "date": "2026-04-16T12:05:00",
            })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "duplicate"
