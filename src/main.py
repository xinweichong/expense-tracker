"""Expense Tracker — main entry point. Starts all services."""
import base64
import logging
import logging.handlers
import os
import sys
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path so `src.*` imports work when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import atexit

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from src.analytics import generate_summary
from src.config import load_config
from src.storage import Storage
from src.categorizer import Categorizer
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob_paynow import UobPaynowParser
from src.parsers.uob_card import UobCardParser
from src.gmail_poller import GmailPoller
from src.telegram_bot import TelegramBotService
from src.webhook import create_webhook_app
from src.web.app import create_dashboard_app
from src.exchange import ExchangeRateService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# In Railway/containers, use /data for persistent storage
_db_env = os.environ.get("EXPENSE_DB_PATH", "")
DB_PATH = _db_env if _db_env else ("/data/expense_tracker.db" if os.path.isdir("/data") else "expense_tracker.db")
CONFIG_PATH = os.environ.get("EXPENSE_CONFIG_PATH", "config.yaml")
SUMMARY_CACHE_DIR = os.environ.get(
    "SUMMARY_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), "..", "data", "summaries")
)
os.makedirs(SUMMARY_CACHE_DIR, exist_ok=True)


def init_db(db_path: str) -> sqlite3.Connection:
    is_new = not os.path.exists(db_path)
    logger.info(f"Database: {db_path} (exists={not is_new})")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
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
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY,
            keywords TEXT,
            icon TEXT
        );
        CREATE TABLE IF NOT EXISTS ingestion_state (
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
    """)
    # Migrate: add exchange_rate column if missing
    try:
        conn.execute("ALTER TABLE transactions ADD COLUMN exchange_rate REAL DEFAULT 1.0")
    except Exception:
        pass
    # Migrate: add type column if missing
    try:
        conn.execute("ALTER TABLE transactions ADD COLUMN type TEXT DEFAULT 'expense'")
    except Exception:
        pass
    # Migrate: add color column to categories if missing
    try:
        conn.execute("ALTER TABLE categories ADD COLUMN color TEXT DEFAULT NULL")
    except Exception:
        pass
    # Migrate: add contributed_date column to goal_contributions if missing
    try:
        conn.execute("ALTER TABLE goal_contributions ADD COLUMN contributed_date TEXT")
    except Exception:
        pass
    # Migrate: add type column to categories if missing
    try:
        conn.execute("ALTER TABLE categories ADD COLUMN type TEXT DEFAULT 'neutral'")
    except Exception:
        pass
    # Populate default type values for known categories
    type_defaults = [
        ("needs",  ("Transport", "Groceries", "Bills & Utilities", "Healthcare", "Housing", "Insurance")),
        ("wants",  ("Dining", "Entertainment", "Shopping", "Travel", "Subscriptions")),
        ("neutral", ("Other", "Transfers", "Income")),
    ]
    for type_val, names in type_defaults:
        placeholders = ",".join("?" * len(names))
        conn.execute(
            f"UPDATE categories SET type = ? WHERE name IN ({placeholders}) AND (type IS NULL OR type = 'neutral')",
            [type_val, *names],
        )
    conn.commit()
    # Create indexes for query performance (idempotent — IF NOT EXISTS)
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_tx_date     ON transactions(DATE(transaction_date))",
        "CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category)",
        "CREATE INDEX IF NOT EXISTS idx_tx_type     ON transactions(type)",
        "CREATE INDEX IF NOT EXISTS idx_tx_merchant ON transactions(merchant)",
    ]
    for stmt in index_statements:
        conn.execute(stmt)
    conn.commit()
    # Seed default app settings (INSERT OR IGNORE — never overwrites user changes)
    defaults = [
        ("anomaly_multiplier", "2.0"),
        ("velocity_alert_threshold", "110"),
        ("budgets_enabled", "false"),
        ("goals_enabled", "false"),
    ]
    for key, value in defaults:
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (key, value)
        )
    conn.commit()
    tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    cat_count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    logger.info(f"Database ready: {tx_count} transactions, {cat_count} categories")
    return conn


def _run_bot(bot: TelegramBotService) -> None:
    """Run the Telegram bot in a background thread using asyncio."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot._loop = loop
    try:
        loop.run_until_complete(bot.app.initialize())
        loop.run_until_complete(bot.app.start())
        loop.run_until_complete(bot.app.post_init(bot.app))  # triggers set_my_commands + menu button
        loop.run_until_complete(bot.app.updater.start_polling())
        loop.run_forever()
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")


def main():
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    # Add file handler after directory is created
    file_handler = logging.handlers.RotatingFileHandler("logs/app.log", maxBytes=10_000_000, backupCount=5)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
    logging.getLogger().addHandler(file_handler)

    config = load_config(CONFIG_PATH)

    # Decode Gmail credentials from environment (for Docker/Railway deployments)
    gmail_config = config.get("gmail", {})
    if gmail_creds_b64 := os.environ.get("GMAIL_CREDENTIALS_JSON"):
        creds_path = gmail_config.get("credentials_file", "credentials.json")
        with open(creds_path, "w") as f:
            f.write(base64.b64decode(gmail_creds_b64).decode())
        logger.info("Decoded Gmail credentials from environment")

    if gmail_token_b64 := os.environ.get("GMAIL_TOKEN_JSON"):
        with open("token.json", "w") as f:
            f.write(base64.b64decode(gmail_token_b64).decode())
        logger.info("Decoded Gmail token from environment")
    else:
        logger.warning("GMAIL_TOKEN_JSON not set — Gmail polling will not work")

    conn = init_db(DB_PATH)
    storage = Storage(connection=conn)

    # Load categories from config
    cat_data = [
        {"name": c["name"], "keywords": ",".join(c.get("keywords", [])), "icon": c.get("icon", "")}
        for c in config.get("categories", [])
    ]
    storage.load_categories(cat_data)
    categorizer = Categorizer(
        config.get("categories", []),
        overrides=storage.get_merchant_overrides(),
    )

    # Set up parsers
    parsers = [DbsPaylahParser(), UobPaynowParser(), UobCardParser()]

    # Set up Gmail poller
    def on_transaction(result, tx_id):
        categorizer.reload_overrides(storage.get_merchant_overrides())
        category, match_source = categorizer.categorize(result.merchant)
        storage.update_transaction(tx_id, category=category)
        bot.notify_transaction(tx_id, result.amount, result.merchant, category, match_source, result.source)

    poller = GmailPoller(
        credentials_path=gmail_config.get("credentials_file", "credentials.json"),
        token_path="token.json",
        sender_filters=gmail_config.get("sender_filters", []),
        parsers=parsers,
        storage=storage,
        on_transaction=on_transaction,
    )

    # Set up Telegram bot
    bot_token = config.get("telegram", {}).get("bot_token", "")
    exchange_config = config.get("exchange_rates", {})
    exchange_service = ExchangeRateService(
        api_url=exchange_config.get("api_url"),
        cache_hours=exchange_config.get("cache_hours", 24),
    )
    server_config = config.get("server", {})
    dashboard_url = server_config.get("webhook_base_url", "")

    bot = TelegramBotService(
        storage=storage, bot_token=bot_token,
        categorizer=categorizer, exchange_service=exchange_service,
        dashboard_url=dashboard_url,
        timezone=config.get("timezone", "Asia/Singapore"),
    )

    # Build combined FastAPI app
    from fastapi import FastAPI
    app = FastAPI()

    # Mount webhook routes
    webhook_app = create_webhook_app(
        storage,
        exchange_service=exchange_service,
        categorizer=categorizer,
        on_transaction=bot.notify_transaction,
    )
    for route in webhook_app.routes:
        app.routes.append(route)

    # Mount dashboard
    dashboard_app = create_dashboard_app(storage, config.get("web", {}).get("password_hash", ""))
    app.mount("/", dashboard_app)

    host = server_config.get("host", "0.0.0.0")
    port = int(os.environ.get("PORT", server_config.get("port", 8080)))

    # Start Gmail poller in background thread
    poll_interval = gmail_config.get("poll_interval_seconds", 120)
    if os.path.exists(gmail_config.get("credentials_file", "credentials.json")):
        poll_thread = threading.Thread(
            target=poller.poll_loop,
            args=(poll_interval,),
            daemon=True,
        )
        poll_thread.start()
        logger.info(f"Gmail poller started (interval: {poll_interval}s)")
    else:
        logger.warning("Gmail credentials not found — skipping email polling")

    # Start Telegram bot in background thread
    if bot_token:
        bot.setup_handlers()
        bot_thread = threading.Thread(target=lambda: _run_bot(bot), daemon=True)
        bot_thread.start()
        logger.info("Telegram bot started")
    else:
        logger.warning("No Telegram bot token — skipping bot")

    # Scheduled summary reports
    if bot_token:
        def _format_and_send_summary(report_type: str) -> None:
            try:
                report = generate_summary(conn, report_type=report_type, cache_dir=SUMMARY_CACHE_DIR)
                arrow = "\u2191" if report["change"] > 0 else "\u2193"
                lines = [
                    f"*{'Weekly' if report_type == 'weekly' else 'Monthly'} Summary*\n",
                    f"*Total spent:* ${report['total_spent']:.2f} ({report['transaction_count']} transactions)",
                ]
                if report["top_category"]:
                    lines.append(f"*Top category:* {report['top_category']['category']} (${report['top_category']['total']:.2f})")
                if report["biggest_transaction"]:
                    bt = report["biggest_transaction"]
                    lines.append(f"*Biggest:* {bt['merchant']} \u2014 ${bt['amount']:.2f}")
                if report["previous_total"] > 0 and report["change_percent"] is not None:
                    lines.append(f"*vs last period:* {arrow} ${abs(report['change']):.2f} ({report['change_percent']:+.1f}%)")
                if report["new_merchant_count"] > 0:
                    lines.append(f"*New merchants:* {report['new_merchant_count']}")
                bot.notify_text("\n".join(lines))
            except Exception as e:
                logger.error(f"Failed to generate/send {report_type} summary: {e}")

        scheduler = BackgroundScheduler()
        scheduler.add_job(lambda: _format_and_send_summary("weekly"), 'cron', day_of_week='sun', hour=9)

        def _monthly_jobs() -> None:
            _format_and_send_summary("monthly")

        scheduler.add_job(_monthly_jobs, 'cron', day=1, hour=9)
        scheduler.add_job(bot.notify_daily_digest, 'cron', hour=9, minute=0)
        scheduler.start()
        atexit.register(lambda: scheduler.shutdown(wait=False))
        logger.info("APScheduler started for weekly/monthly summaries")

    # Start web server (blocking)
    logger.info(f"Starting web server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
