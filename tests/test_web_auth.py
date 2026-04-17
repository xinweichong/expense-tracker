import pytest
from src.web.auth import verify_password, create_session, verify_session


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
    def test_create_and_verify_session(self):
        token = create_session()
        assert verify_session(token) is True

    def test_invalid_session(self):
        assert verify_session("invalid-token") is False
