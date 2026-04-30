import sqlite3
import pytest
from src.web.auth import verify_password, create_session, verify_session
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
    auth._conn = None


class TestPasswordVerify:
    def test_correct_password(self):
        import bcrypt
        hashed = bcrypt.hashpw(b"test-password", bcrypt.gensalt()).decode()
        assert verify_password("test-password", hashed) is True

    def test_wrong_password(self):
        import bcrypt
        hashed = bcrypt.hashpw(b"test-password", bcrypt.gensalt()).decode()
        assert verify_password("wrong-password", hashed) is False


class TestSessionManagement:
    def test_create_and_verify_session(self, auth_conn):
        token = create_session()
        assert verify_session(token) is True

    def test_invalid_session(self, auth_conn):
        assert verify_session("invalid-token") is False
