import pytest
import sqlite3
import tempfile
import os
from pathlib import Path


@pytest.fixture
def in_memory_db():
    """Provide an in-memory SQLite connection with schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
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
        color TEXT
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
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id    INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
        amount     REAL NOT NULL,
        month      TEXT NOT NULL,
        source     TEXT NOT NULL DEFAULT 'auto',
        note       TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """
    conn.executescript(schema)
    yield conn
    conn.close()


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
