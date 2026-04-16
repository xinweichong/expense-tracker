import pytest
import pytest_asyncio
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
            "card_last4": "DBS Debit",
            "date": "16/04/2026 12:30:00",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "transaction_id" in data

    @pytest.mark.asyncio
    async def test_missing_amount_returns_400(self, client):
        response = await client.post("/webhook/apple-wallet", json={
            "merchant": "Test",
            "card_last4": "1234",
            "date": "16/04/2026 12:00:00",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_merchant_returns_400(self, client):
        response = await client.post("/webhook/apple-wallet", json={
            "amount": "-10.0",
            "card_last4": "1234",
            "date": "16/04/2026 12:00:00",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_within_window_returns_200(self, client, in_memory_db):
        payload = {
            "amount": "-12.50",
            "merchant": "Toast Box",
            "card_last4": "DBS Debit",
            "date": "16/04/2026 12:30:00",
        }
        r1 = await client.post("/webhook/apple-wallet", json=payload)
        assert r1.status_code == 200
        r2 = await client.post("/webhook/apple-wallet", json=payload)
        assert r2.status_code == 200
        assert r2.json()["status"] == "duplicate"
