import secrets
import bcrypt

# In-memory session store
_sessions: set[str] = set()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session() -> str:
    token = secrets.token_hex(32)
    _sessions.add(token)
    return token


def verify_session(token: str) -> bool:
    return token in _sessions


def destroy_session(token: str) -> None:
    _sessions.discard(token)
