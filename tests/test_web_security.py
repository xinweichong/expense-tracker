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
        yield ac


@pytest_asyncio.fixture
async def authed_client(dashboard_app):
    transport = ASGITransport(app=dashboard_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/api/login", json={"password": "test-password"})
        yield ac


class TestPing:
    @pytest.mark.asyncio
    async def test_ping_returns_ok_when_authenticated(self, authed_client):
        r = await authed_client.get("/api/ping")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_ping_returns_401_when_not_authenticated(self, client):
        r = await client.get("/api/ping")
        assert r.status_code == 401


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout_clears_session(self, authed_client):
        # Confirm authenticated first
        r = await authed_client.get("/api/ping")
        assert r.status_code == 200
        # Logout
        r = await authed_client.post("/api/logout")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
        # Should now be unauthenticated
        r = await authed_client.get("/api/ping")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_without_session_is_ok(self, client):
        r = await client.post("/api/logout")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
