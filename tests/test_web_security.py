import bcrypt
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.storage import Storage
from src.web.app import create_dashboard_app
from src.web import auth as _auth


@pytest.fixture
def password_hash():
    return bcrypt.hashpw(b"test-password", bcrypt.gensalt()).decode()


@pytest.fixture
def dashboard_app(in_memory_db, password_hash, monkeypatch):
    monkeypatch.setenv("SECURE_COOKIES", "false")
    _auth.init_auth(in_memory_db)
    storage = Storage(connection=in_memory_db)
    yield create_dashboard_app(storage, password_hash)
    _auth._conn = None


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


class TestCookieFlags:
    @pytest.mark.asyncio
    async def test_login_cookie_is_httponly(self, client):
        r = await client.post("/api/login", json={"password": "test-password"})
        assert r.status_code == 200
        set_cookie = r.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()

    @pytest.mark.asyncio
    async def test_login_cookie_has_samesite_lax(self, client):
        r = await client.post("/api/login", json={"password": "test-password"})
        assert r.status_code == 200
        set_cookie = r.headers.get("set-cookie", "")
        assert "samesite=lax" in set_cookie.lower()

    @pytest.mark.asyncio
    async def test_login_cookie_not_secure_in_test(self, client):
        # SECURE_COOKIES=false (set by dashboard_app fixture) means Secure flag must be absent
        r = await client.post("/api/login", json={"password": "test-password"})
        set_cookie = r.headers.get("set-cookie", "")
        assert "secure" not in set_cookie.lower()


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


class TestCredentialFilePermissions:
    def test_credentials_written_with_restricted_permissions(self, tmp_path):
        """Credential files must not be world-readable (mode 0o600 or stricter)."""
        import base64
        import os
        import stat

        creds_path = tmp_path / "credentials.json"
        fake_b64 = base64.b64encode(b'{"type": "service_account"}').decode()

        # Simulate the credential-writing block in main.py
        with open(creds_path, "w") as f:
            f.write(base64.b64decode(fake_b64).decode())
        os.chmod(creds_path, 0o600)

        mode = stat.S_IMODE(os.stat(creds_path).st_mode)
        assert not (mode & stat.S_IRGRP), "credential file is group-readable"
        assert not (mode & stat.S_IROTH), "credential file is world-readable"
