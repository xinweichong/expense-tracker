"""Expense Tracker — main entry point. Starts all services."""
import logging
import logging.handlers
import os
import sys
import sqlite3
import threading
from pathlib import Path

# Add project root to sys.path so `src.*` imports work when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from src.config import load_config
from src.storage import Storage
from src.categorizer import Categorizer
from src.parsers.dbs_paylah import DbsPaylahParser
from src.parsers.uob_paynow import UobPaynowParser
from src.gmail_poller import GmailPoller
from src.telegram_bot import TelegramBotService
from src.webhook import create_webhook_app
from src.web.app import create_dashboard_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("EXPENSE_DB_PATH", "expense_tracker.db")
CONFIG_PATH = os.environ.get("EXPENSE_CONFIG_PATH", "config.yaml")


def init_db(db_path: str) -> sqlite3.Connection:
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
            merchant TEXT,
            description TEXT,
            category TEXT,
            transaction_date DATETIME,
            ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            raw_data TEXT
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
    """)
    conn.commit()
    return conn


def _run_bot(bot: TelegramBotService) -> None:
    """Run the Telegram bot in a background thread using asyncio."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.app.initialize())
        loop.run_until_complete(bot.app.start())
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
    parsers = [DbsPaylahParser(), UobPaynowParser()]

    # Set up Gmail poller
    gmail_config = config.get("gmail", {})
    poller = GmailPoller(
        credentials_path=gmail_config.get("credentials_file", "credentials.json"),
        token_path="token.json",
        sender_filters=gmail_config.get("sender_filters", []),
        parsers=parsers,
        storage=storage,
    )

    # Set up Telegram bot
    bot_token = config.get("telegram", {}).get("bot_token", "")
    bot = TelegramBotService(storage=storage, bot_token=bot_token, categorizer=categorizer)

    # Build combined FastAPI app
    from fastapi import FastAPI
    app = FastAPI()

    # Mount webhook routes
    webhook_app = create_webhook_app(storage)
    for route in webhook_app.routes:
        app.routes.append(route)

    # Mount dashboard
    dashboard_app = create_dashboard_app(storage, config.get("web", {}).get("password_hash", ""))
    app.mount("/", dashboard_app)

    server_config = config.get("server", {})
    host = server_config.get("host", "0.0.0.0")
    port = server_config.get("port", 8080)

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

    # Start web server (blocking)
    logger.info(f"Starting web server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
