import secrets
import sqlite3
import bcrypt
from typing import Optional

_conn: Optional[sqlite3.Connection] = None


def init_auth(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_session() -> str:
    if _conn is None:
        raise RuntimeError("auth not initialized — call init_auth(conn) first")
    token = secrets.token_hex(32)
    _conn.execute("INSERT INTO sessions (token) VALUES (?)", (token,))
    _conn.commit()
    return token


def verify_session(token: str) -> bool:
    if _conn is None:
        return False
    row = _conn.execute(
        "SELECT 1 FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    return row is not None


def destroy_session(token: str) -> None:
    if _conn is None:
        return
    _conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    _conn.commit()
