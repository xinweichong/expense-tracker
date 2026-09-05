"""Shared test helpers for dashboard app fixtures."""
import sqlite3
import bcrypt

TEST_USERNAME = "testuser"
TEST_PASSWORD = "test-password"


class FakeContext:
    def __init__(self, storage):
        self.storage = storage
        self.poller = None


class FakeUserManager:
    """Single-user stub — always returns the same context regardless of username.
    Used by existing tests to keep them simple. For isolation tests use FakeMultiUserManager."""
    def __init__(self, storage):
        self._ctx = FakeContext(storage)

    def get(self, username):
        return self._ctx

    def start_poller(self, username):
        pass


class FakeMultiUserManager:
    """Multi-user routing stub — routes get(username) to the correct per-user context."""
    def __init__(self, contexts: dict):
        """contexts: {username: storage_instance}"""
        self._ctxs = {u: FakeContext(s) for u, s in contexts.items()}

    def get(self, username):
        return self._ctxs.get(username)

    def start_poller(self, username):
        pass


def make_admin_db_with_user(password: str = TEST_PASSWORD):
    """Return an in-memory app.db connection pre-seeded with TEST_USERNAME."""
    from src.storage import AdminStorage
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
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
            force_password_change INTEGER DEFAULT 0,
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
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn.execute(
        """INSERT INTO users (username, password_hash, onboarding_complete, force_password_change)
           VALUES (?, ?, 1, 0)""",
        (TEST_USERNAME, pw_hash),
    )
    conn.commit()
    return conn


def make_admin_db_schema():
    """Return a bare in-memory app.db connection with the schema but no users."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
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
            force_password_change INTEGER DEFAULT 0,
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
    conn.commit()
    return conn

