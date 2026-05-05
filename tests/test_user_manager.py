"""Tests for UserManager — the per-user service registry."""
import os
import sqlite3
import tempfile

import bcrypt
import pytest

from src.storage import Storage, AdminStorage
from src.user_manager import UserContext, UserManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin_storage():
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
    return AdminStorage(conn)


def _make_user_manager(data_dir, admin_storage, **kwargs):
    return UserManager(
        data_dir=data_dir,
        config={
            "timezone": "Asia/Singapore",
            "gmail": {"credentials_file": "credentials.json", "poll_interval_seconds": 120,
                      "sender_filters": []},
        },
        exchange_service=None,
        parsers=[],
        scheduler=None,
        bot=None,
        admin_storage=admin_storage,
        **kwargs,
    )


PW_HASH = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()


# ---------------------------------------------------------------------------
# UserContext
# ---------------------------------------------------------------------------

class TestUserContext:
    def test_dataclass_fields(self):
        storage = object()
        categorizer = object()
        ctx = UserContext(
            username="alice",
            storage=storage,
            categorizer=categorizer,
            poller=None,
            db_path="/data/users/alice/expense_tracker.db",
            token_path="/data/users/alice/token.json",
        )
        assert ctx.username == "alice"
        assert ctx.storage is storage
        assert ctx.poller is None


# ---------------------------------------------------------------------------
# UserManager.create_user
# ---------------------------------------------------------------------------

class TestCreateUser:
    def test_create_user_returns_context(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        ctx = um.create_user("alice", PW_HASH)
        assert isinstance(ctx, UserContext)
        assert ctx.username == "alice"

    def test_create_user_writes_user_to_admin_db(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        um.create_user("alice", PW_HASH)
        user = admin.get_user("alice")
        assert user is not None
        assert user["username"] == "alice"

    def test_create_user_initialises_db_on_disk(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        um.create_user("alice", PW_HASH)
        db_path = os.path.join(str(tmp_path), "users", "alice", "expense_tracker.db")
        assert os.path.exists(db_path)

    def test_create_user_registered_in_registry(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        um.create_user("alice", PW_HASH)
        assert um.get("alice") is not None

    def test_create_user_storage_is_usable(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        ctx = um.create_user("alice", PW_HASH)
        # Storage should be initialised and accept inserts
        tx_id = ctx.storage.insert_transaction(
            source="manual", source_id="m-001",
            amount=10.0, merchant="Test", transaction_date="2026-01-01T12:00:00",
        )
        assert isinstance(tx_id, int)


# ---------------------------------------------------------------------------
# UserManager.get / get_by_chat_id
# ---------------------------------------------------------------------------

class TestGetUser:
    def test_get_unknown_user_returns_none(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        assert um.get("nobody") is None

    def test_get_by_chat_id_returns_context(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        um.create_user("alice", PW_HASH)
        admin.update_user("alice", telegram_chat_id="12345")
        ctx = um.get_by_chat_id(12345)
        assert ctx is not None
        assert ctx.username == "alice"

    def test_get_by_chat_id_unknown_returns_none(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        assert um.get_by_chat_id(99999) is None


# ---------------------------------------------------------------------------
# UserManager.load_all_users
# ---------------------------------------------------------------------------

class TestLoadAllUsers:
    def test_load_all_users_populates_registry(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        # Pre-create users on disk as load_all_users would find them in admin_storage
        um.create_user("alice", PW_HASH)
        um.create_user("bob", PW_HASH)
        # Reset registry to simulate fresh startup
        um._registry.clear()
        um.load_all_users()
        assert um.get("alice") is not None
        assert um.get("bob") is not None

    def test_load_all_users_skips_missing_db(self, tmp_path):
        """A user in app.db whose db file is missing should be skipped, not crash."""
        admin = _make_admin_storage()
        admin.create_user("ghost", PW_HASH)
        um = _make_user_manager(str(tmp_path), admin)
        # No DB file on disk for ghost — should not raise
        um.load_all_users()
        assert um.get("ghost") is None


# ---------------------------------------------------------------------------
# UserManager.delete_user
# ---------------------------------------------------------------------------

class TestDeleteUser:
    def test_delete_user_removes_from_registry(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        um.create_user("alice", PW_HASH)
        um.delete_user("alice")
        assert um.get("alice") is None

    def test_delete_unknown_user_is_noop(self, tmp_path):
        admin = _make_admin_storage()
        um = _make_user_manager(str(tmp_path), admin)
        um.delete_user("nobody")  # must not raise
