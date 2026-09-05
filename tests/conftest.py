import pytest
import sqlite3
import os
import sys
import bcrypt

# Make the tests/ directory importable so test files can do `from helpers import ...`
sys.path.insert(0, os.path.dirname(__file__))


@pytest.fixture(autouse=True)
def disable_secure_cookies(monkeypatch):
    """Disable Secure cookie flag in tests — httpx uses http:// transport."""
    monkeypatch.setenv("SECURE_COOKIES", "false")


@pytest.fixture
def in_memory_db():
    """Provide an in-memory SQLite connection with schema applied."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    schema = """
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT UNIQUE,
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'SGD',
        exchange_rate REAL DEFAULT 1.0,
        merchant TEXT,
        description TEXT,
        category TEXT,
        transaction_date DATETIME,
        ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        raw_data TEXT,
        type TEXT DEFAULT 'expense'
    );

    CREATE TABLE categories (
        name TEXT PRIMARY KEY,
        keywords TEXT,
        icon TEXT,
        color TEXT,
        type TEXT DEFAULT 'neutral'
    );

    CREATE TABLE ingestion_state (
        source TEXT PRIMARY KEY,
        last_processed_id TEXT,
        last_processed_at DATETIME,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS merchant_overrides (
        merchant TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        source TEXT DEFAULT 'manual',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS recurring_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant TEXT NOT NULL,
        avg_amount REAL NOT NULL,
        frequency TEXT NOT NULL,
        category TEXT,
        first_seen DATETIME,
        last_seen DATETIME,
        occurrences INTEGER DEFAULT 2
    );

    CREATE TABLE IF NOT EXISTS merchant_tags (
        merchant   TEXT PRIMARY KEY,
        tags       TEXT DEFAULT '',
        notes      TEXT DEFAULT '',
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS app_settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS budgets (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        category   TEXT,
        period     TEXT NOT NULL DEFAULT 'monthly',
        amount     REAL NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(category, period)
    );

    CREATE TABLE IF NOT EXISTS goals (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT NOT NULL,
        target_amount REAL NOT NULL,
        saved_amount  REAL NOT NULL DEFAULT 0,
        target_date   DATE,
        status        TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'completed', 'paused')),
        created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS goal_contributions (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id          INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
        amount           REAL NOT NULL,
        month            TEXT NOT NULL,
        contributed_date TEXT,
        source           TEXT NOT NULL DEFAULT 'auto',
        note             TEXT,
        created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS trips (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT NOT NULL,
        destination      TEXT,
        start_date       DATE NOT NULL,
        end_date         DATE,
        primary_currency TEXT DEFAULT 'SGD',
        status           TEXT NOT NULL DEFAULT 'inactive',
        created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS trip_transactions (
        trip_id        INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
        transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
        added_by       TEXT DEFAULT 'auto',
        PRIMARY KEY (trip_id, transaction_id)
    );

    CREATE TABLE IF NOT EXISTS subscriptions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant    TEXT NOT NULL,
        label       TEXT,
        frequency   TEXT NOT NULL,
        billing_day INTEGER,
        status      TEXT DEFAULT 'active',
        notes       TEXT,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS upcoming_transactions (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        subscription_id         INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
        expected_date           TEXT NOT NULL,
        expected_amount         REAL,
        matched_transaction_id  INTEGER REFERENCES transactions(id),
        status                  TEXT DEFAULT 'pending',
        created_at              DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('subscriptions_enabled', 'false');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('recurring_enabled', 'false');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_weekly_insight_content', '');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_weekly_insight_generated_at', '');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_monthly_insight_content', '');
    INSERT OR IGNORE INTO app_settings (key, value) VALUES ('llm_monthly_insight_generated_at', '');
    """
    conn.executescript(schema)
    yield conn
    conn.close()


@pytest.fixture
def in_memory_admin_db():
    """Provide an in-memory SQLite connection with the app.db schema applied."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE users (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            username              TEXT UNIQUE NOT NULL,
            password_hash         TEXT NOT NULL,
            telegram_chat_id      TEXT,
            gmail_connected       INTEGER DEFAULT 0,
            wants_gmail           INTEGER DEFAULT 1,
            wants_apple_wallet    INTEGER DEFAULT 1,
            onboarding_complete   INTEGER DEFAULT 0,
            force_password_change INTEGER DEFAULT 0,
            created_at            DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE sessions (
            token           TEXT PRIMARY KEY,
            username        TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
            user_agent      TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE admin_sessions (
            token           TEXT PRIMARY KEY,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE telegram_link_tokens (
            token       TEXT PRIMARY KEY,
            username    TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
            expires_at  DATETIME NOT NULL
        );
    """)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def sample_categories():
    return [
        {"name": "Food", "keywords": "restaurant,cafe,food,kopitiam,toast box,ya kun", "icon": "🍜"},
        {"name": "Transport", "keywords": "grab,gojek,comfortdelgro,mrt,bus,taxi,cdg", "icon": "🚗"},
        {"name": "Shopping", "keywords": "shopee,lazada,fairprice,cold storage,ntuc", "icon": "🛒"},
        {"name": "Bills", "keywords": "sp services,singtel,starhub,m1", "icon": "📄"},
        {"name": "Entertainment", "keywords": "netflix,spotify", "icon": "🎬"},
        {"name": "Other", "keywords": "", "icon": "📌"},
    ]


@pytest.fixture
def sample_config():
    return {
        "gmail": {
            "credentials_file": "credentials.json",
            "poll_interval_seconds": 120,
            "sender_filters": ["notification@dbs.com", "notification@uob.com"],
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8080,
            "webhook_base_url": "https://example.com",
        },
        "web": {
            "password_hash": "$2b$12$examplehashedpassword",
        },
        "telegram": {
            "bot_token": "test-token-123",
        },
        "categories": [
            {"name": "Food", "keywords": ["restaurant", "cafe", "food"], "icon": "🍜"},
            {"name": "Transport", "keywords": ["grab", "gojek"], "icon": "🚗"},
            {"name": "Other", "keywords": [], "icon": "📌"},
        ],
    }
