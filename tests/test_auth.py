import sqlite3
import pytest
from src.web import auth


@pytest.fixture
def auth_conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE sessions (
            token TEXT PRIMARY KEY,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    auth.init_auth(conn)
    yield conn
    conn.close()
    auth._conn = None  # reset module state after test


def test_create_and_verify_session(auth_conn):
    token = auth.create_session()
    assert len(token) == 64  # secrets.token_hex(32) → 64 hex chars
    assert auth.verify_session(token) is True


def test_verify_unknown_token_returns_false(auth_conn):
    assert auth.verify_session("nonexistent") is False


def test_destroy_session(auth_conn):
    token = auth.create_session()
    assert auth.verify_session(token) is True
    auth.destroy_session(token)
    assert auth.verify_session(token) is False


def test_destroy_nonexistent_session_is_noop(auth_conn):
    auth.destroy_session("does-not-exist")  # must not raise


def test_sessions_persisted_in_db(auth_conn):
    token = auth.create_session()
    row = auth_conn.execute(
        "SELECT token FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    assert row is not None


def test_verify_session_without_init_returns_false():
    import importlib
    fresh_auth = importlib.import_module("src.web.auth")
    fresh_auth._conn = None
    assert fresh_auth.verify_session("anything") is False
