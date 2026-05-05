import bcrypt
from typing import Optional

_admin_storage = None   # set by init_auth()


def init_auth(admin_storage) -> None:
    """Called once at startup with the AdminStorage instance."""
    global _admin_storage
    _admin_storage = admin_storage


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session(username: str, user_agent: str = "") -> str:
    """Create a session for a user. Returns the session token."""
    return _admin_storage.create_session(username, user_agent)


def verify_session(token: str) -> Optional[str]:
    """Returns username if session is valid and within 30-day sliding window.
    Returns None if invalid or expired.
    """
    if _admin_storage is None:
        return None
    return _admin_storage.verify_session(token)


def destroy_session(token: str) -> None:
    if _admin_storage is not None:
        _admin_storage.destroy_session(token)
