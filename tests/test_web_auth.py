import sqlite3
import pytest
import bcrypt
from src.storage import AdminStorage
from src.web.auth import verify_password, create_session, verify_session, destroy_session, init_auth
from src.web import auth


def _make_admin_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            telegram_chat_id TEXT,
            gmail_connected INTEGER DEFAULT 0,
            wants_gmail INTEGER DEFAULT 1,
            wants_apple_wallet INTEGER DEFAULT 1,
            onboarding_complete INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
            user_agent TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE admin_sessions (
            token TEXT PRIMARY KEY,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE telegram_link_tokens (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
            expires_at DATETIME NOT NULL
        );
    """)
    return conn


@pytest.fixture(autouse=True)
def reset_auth():
    """Reset auth module state between tests."""
    yield
    auth._admin_storage = None


@pytest.fixture
def auth_storage():
    conn = _make_admin_db()
    storage = AdminStorage(conn)
    storage.create_user("testuser", "hash")
    init_auth(storage)
    return storage


class TestPasswordVerify:
    def test_correct_password(self):
        hashed = bcrypt.hashpw(b"test-password", bcrypt.gensalt()).decode()
        assert verify_password("test-password", hashed) is True

    def test_wrong_password(self):
        hashed = bcrypt.hashpw(b"test-password", bcrypt.gensalt()).decode()
        assert verify_password("wrong-password", hashed) is False


class TestSessionManagement:
    def test_create_and_verify_session(self, auth_storage):
        token = create_session("testuser")
        assert verify_session(token) == "testuser"

    def test_invalid_session(self, auth_storage):
        assert verify_session("invalid-token") is None

    def test_destroy_session(self, auth_storage):
        token = create_session("testuser")
        destroy_session(token)
        assert verify_session(token) is None
