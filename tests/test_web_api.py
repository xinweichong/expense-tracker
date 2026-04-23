import bcrypt
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.storage import Storage
from src.web.app import create_dashboard_app


@pytest.fixture
def password_hash():
    return bcrypt.hashpw(b"test-password", bcrypt.gensalt()).decode()


@pytest.fixture
def dashboard_app(in_memory_db, password_hash):
    storage = Storage(connection=in_memory_db)
    return create_dashboard_app(storage, password_hash)


@pytest_asyncio.fixture
async def client(dashboard_app):
    transport = ASGITransport(app=dashboard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Log in to get a session cookie
        await ac.post("/api/login", json={"password": "test-password"})
        yield ac


class TestCreateTransaction:
    @pytest.mark.asyncio
    async def test_create_expense(self, client):
        response = await client.post("/api/transactions", json={
            "amount": 12.50,
            "merchant": "Toast Box",
            "category": "Food",
            "type": "expense",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == 12.50
        assert data["merchant"] == "Toast Box"
        assert data["category"] == "Food"
        assert data["type"] == "expense"
        assert data["source"] == "manual"
        assert data["currency"] == "SGD"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_income(self, client):
        response = await client.post("/api/transactions", json={
            "amount": 5000.00,
            "merchant": "Employer",
            "category": "Salary",
            "type": "income",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["amount"] == 5000.00
        assert data["type"] == "income"
        assert data["category"] == "Salary"

    @pytest.mark.asyncio
    async def test_create_cash_transaction(self, client):
        response = await client.post("/api/transactions", json={
            "amount": 5.00,
            "merchant": "Hawker Stall",
            "category": "Food",
            "type": "expense",
            "source": "cash",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "cash"
        assert data["amount"] == 5.00

    @pytest.mark.asyncio
    async def test_create_with_foreign_currency(self, client):
        response = await client.post("/api/transactions", json={
            "amount": 350.00,
            "merchant": "Thai Restaurant BKK",
            "category": "Food",
            "type": "expense",
            "currency": "THB",
            "exchange_rate": 0.039,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["currency"] == "THB"
        assert data["exchange_rate"] == 0.039
        assert data["amount"] == 350.00

    @pytest.mark.asyncio
    async def test_create_missing_amount_returns_400(self, client):
        response = await client.post("/api/transactions", json={
            "merchant": "Test",
            "type": "expense",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_invalid_type_returns_400(self, client):
        response = await client.post("/api/transactions", json={
            "amount": 10.00,
            "type": "transfer",
        })
        assert response.status_code == 400


class TestListTransactions:
    @pytest.mark.asyncio
    async def test_list_transactions_with_limit(self, client):
        # Create 3 transactions
        for i in range(3):
            await client.post("/api/transactions", json={
                "amount": 10.0 + i,
                "merchant": f"Shop {i}",
                "type": "expense",
            })

        response = await client.get("/api/transactions?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestUpdateTransaction:
    @pytest.mark.asyncio
    async def test_update_transaction(self, client):
        create_resp = await client.post("/api/transactions", json={
            "amount": 15.00,
            "merchant": "Old Name",
            "category": "Food",
            "type": "expense",
        })
        assert create_resp.status_code == 200
        tx_id = create_resp.json()["id"]

        update_resp = await client.put(f"/api/transactions/{tx_id}", json={
            "merchant": "New Name",
            "amount": 20.00,
            "category": "Shopping",
        })
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["merchant"] == "New Name"
        assert data["amount"] == 20.00
        assert data["category"] == "Shopping"
        assert data["id"] == tx_id

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_404(self, client):
        response = await client.put("/api/transactions/99999", json={
            "merchant": "Ghost",
        })
        assert response.status_code == 404


class TestDeleteTransaction:
    @pytest.mark.asyncio
    async def test_delete_transaction(self, client):
        create_resp = await client.post("/api/transactions", json={
            "amount": 8.00,
            "merchant": "To Delete",
            "type": "expense",
        })
        assert create_resp.status_code == 200
        tx_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/transactions/{tx_id}")
        assert delete_resp.status_code == 200

        # Verify it's gone
        get_resp = await client.get(f"/api/transactions/{tx_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, client):
        response = await client.delete("/api/transactions/99999")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_settings_returns_defaults(client):
    """GET /api/settings should return the two default threshold values."""
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["anomaly_multiplier"] == 2.0
    assert data["velocity_alert_threshold"] == 110

@pytest.mark.asyncio
async def test_put_settings_updates_values(client):
    """PUT /api/settings should persist new threshold values."""
    resp = await client.put("/api/settings", json={
        "anomaly_multiplier": 3.0,
        "velocity_alert_threshold": 120,
    })
    assert resp.status_code == 200
    # Verify persisted
    resp2 = await client.get("/api/settings")
    assert resp2.json()["anomaly_multiplier"] == 3.0
    assert resp2.json()["velocity_alert_threshold"] == 120

@pytest.mark.asyncio
async def test_put_settings_rejects_out_of_range(client):
    """PUT /api/settings should reject values outside allowed range."""
    resp = await client.put("/api/settings", json={"anomaly_multiplier": 0.5})
    assert resp.status_code == 422

@pytest.mark.asyncio
async def test_put_settings_rejects_velocity_out_of_range(client):
    resp = await client.put("/api/settings", json={"velocity_alert_threshold": 30})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_put_settings_atomic_on_mixed_valid_invalid(client):
    """When one field is invalid, no settings should be written."""
    # Set a known starting state
    await client.put("/api/settings", json={"velocity_alert_threshold": 150})
    # Now send a mixed request: one valid, one invalid
    resp = await client.put("/api/settings", json={
        "anomaly_multiplier": 0.5,      # invalid
        "velocity_alert_threshold": 200, # valid
    })
    assert resp.status_code == 422
    # velocity_alert_threshold should remain 150, not 200
    resp2 = await client.get("/api/settings")
    assert resp2.json()["velocity_alert_threshold"] == 150
