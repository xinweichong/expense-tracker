"""UserManager — central registry for per-user service instances.

This is the only place Storage and GmailPoller are ever instantiated.
main.py and web/app.py never create them directly.
"""
import logging
import os
import sqlite3
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    username: str
    storage: object          # Storage instance
    categorizer: object      # Categorizer instance
    poller: object           # GmailPoller instance (not always running)
    db_path: str
    token_path: str


class UserManager:
    def __init__(
        self,
        data_dir: str,
        config: dict,
        exchange_service,
        parsers: list,
        scheduler,
        bot,
        admin_storage,
    ):
        self._data_dir = data_dir
        self._config = config
        self._exchange_service = exchange_service
        self._parsers = parsers
        self._scheduler = scheduler
        self._bot = bot
        self._admin_storage = admin_storage
        self._registry: dict[str, UserContext] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, username: str) -> Optional[UserContext]:
        """Return the live context for a user, or None if unknown."""
        return self._registry.get(username)

    def get_by_chat_id(self, chat_id: int) -> Optional[UserContext]:
        """Resolve a Telegram chat_id to a UserContext via admin_storage."""
        user = self._admin_storage.get_user_by_chat_id(str(chat_id))
        if user is None:
            return None
        return self._registry.get(user["username"])

    def load_all_users(self) -> None:
        """Called once at startup. For each user in app.db, construct their
        UserContext; if their DB file exists and Gmail is connected, start
        the poller thread.
        """
        for user in self._admin_storage.list_users():
            username = user["username"]
            db_path = self._user_db_path(username)
            if not os.path.exists(db_path):
                logger.warning("Skipping user %s — DB file missing: %s", username, db_path)
                continue
            try:
                ctx = self._build_context(username, db_path)
                self._registry[username] = ctx
                if user["gmail_connected"]:
                    ctx.poller.start()
                logger.info(
                    "Loaded user %s: Gmail %s Telegram %s",
                    username,
                    "connected" if user["gmail_connected"] else "not connected",
                    "linked" if user["telegram_chat_id"] else "not linked",
                )
            except Exception as e:
                logger.error("Failed to load user %s: %s", username, e)

    def create_user(self, username: str, password_hash: str) -> UserContext:
        """Create a new user account, initialise their DB, and register them."""
        user_dir = os.path.join(self._data_dir, "users", username)
        os.makedirs(user_dir, exist_ok=True)

        db_path = os.path.join(user_dir, "expense_tracker.db")
        _init_user_db(db_path)

        # Record in admin DB (no-op if already exists)
        if self._admin_storage.get_user(username) is None:
            self._admin_storage.create_user(username, password_hash)

        ctx = self._build_context(username, db_path)
        self._registry[username] = ctx
        self._register_scheduler_jobs(username)
        return ctx

    def start_poller(self, username: str) -> None:
        """Start the already-constructed GmailPoller thread for a user.
        Called only after Gmail OAuth completes successfully.
        """
        ctx = self._registry[username]
        ctx.poller.start()

    def delete_user(self, username: str) -> None:
        """Remove a user from the registry and stop their services.
        Does NOT delete files on disk.
        """
        ctx = self._registry.pop(username, None)
        if ctx and ctx.poller:
            ctx.poller.stop()
        for job_id in [f"weekly_{username}", f"monthly_{username}", f"daily_{username}"]:
            if self._scheduler is not None:
                try:
                    self._scheduler.remove_job(job_id)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _user_db_path(self, username: str) -> str:
        return os.path.join(self._data_dir, "users", username, "expense_tracker.db")

    def _user_token_path(self, username: str) -> str:
        return os.path.join(self._data_dir, "users", username, "token.json")

    def _build_context(self, username: str, db_path: str) -> UserContext:
        """Construct Storage, Categorizer, and GmailPoller for one user."""
        from src.storage import Storage
        from src.categorizer import Categorizer
        from src.gmail_poller import GmailPoller

        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        storage = Storage(conn)

        categories = self._config.get("categories", [])
        categorizer = Categorizer(categories)

        token_path = self._user_token_path(username)
        gmail_cfg = self._config.get("gmail", {})
        credentials_path = gmail_cfg.get("credentials_file", "credentials.json")
        poll_interval = int(gmail_cfg.get("poll_interval_seconds", 120))
        sender_filters = gmail_cfg.get("sender_filters", [])

        poller = GmailPoller(
            credentials_path=credentials_path,
            token_path=token_path,
            sender_filters=sender_filters,
            parsers=self._parsers,
            storage=storage,
            on_transaction=self._make_on_transaction(username, storage, categorizer),
            on_auth_error=self._make_on_auth_error(username),
            poll_interval=poll_interval,
        )
        # Attach exchange_service and categorizer to context for webhook direct path
        ctx = UserContext(
            username=username,
            storage=storage,
            categorizer=categorizer,
            poller=poller,
            db_path=db_path,
            token_path=token_path,
        )
        # Back-reference so webhook can reach exchange_service
        ctx.exchange_service = self._exchange_service  # type: ignore[attr-defined]
        return ctx

    def _make_on_transaction(self, username: str, storage, categorizer):
        bot = self._bot

        def on_transaction(tx_dict: dict) -> None:
            if bot is None:
                return
            try:
                tx_id = tx_dict["id"]
                amount = float(tx_dict.get("amount", 0))
                merchant = tx_dict.get("merchant", "")
                category = tx_dict.get("category")
                source = tx_dict.get("source", "")
                # Pipeline-ingested transactions are already categorized — treat as "ingest"
                bot.notify_transaction(tx_id, amount, merchant, category, "ingest", source, username=username)
            except Exception as e:
                logger.warning("notify_transaction failed for %s: %s", username, e)

        return on_transaction

    def _make_on_auth_error(self, username: str):
        bot = self._bot

        def on_auth_error(message: str) -> None:
            if bot is not None:
                try:
                    bot.notify_text(
                        f"Gmail authentication error — please re-connect via the Cashe onboarding page.\n`{message}`",
                        username,
                    )
                except Exception as e:
                    logger.warning("notify_text (auth_error) failed for %s: %s", username, e)

        return on_auth_error

    def _register_scheduler_jobs(self, username: str) -> None:
        """Register weekly/monthly/daily summary APScheduler jobs for one user."""
        if self._scheduler is None:
            return
        ctx = self.get(username)
        tz = self._config.get("timezone", "Asia/Singapore")
        bot = self._bot

        def weekly():
            if bot and ctx:
                bot.notify_text(_weekly_summary(ctx.storage), username)

        def monthly():
            if bot and ctx:
                bot.notify_text(_monthly_summary(ctx.storage), username)

        def daily():
            if bot:
                bot.notify_daily_digest(username)

        self._scheduler.add_job(
            weekly, "cron", day_of_week="sun", hour=8, timezone=tz,
            id=f"weekly_{username}", replace_existing=True,
        )
        self._scheduler.add_job(
            monthly, "cron", day=1, hour=8, timezone=tz,
            id=f"monthly_{username}", replace_existing=True,
        )
        self._scheduler.add_job(
            daily, "cron", hour=8, minute=0, timezone=tz,
            id=f"daily_{username}", replace_existing=True,
        )


# ---------------------------------------------------------------------------
# DB initialisation (extracted so it can be called without a full UserManager)
# ---------------------------------------------------------------------------

def _init_user_db(db_path: str) -> sqlite3.Connection:
    """Initialise (or open) a user's expense_tracker.db with the full schema."""
    # Reuse the init_db logic from main.py by importing it at call time to
    # avoid circular imports (main.py imports UserManager).
    from src.main import init_db
    return init_db(db_path)


# ---------------------------------------------------------------------------
# Summary helpers (used by scheduler jobs)
# ---------------------------------------------------------------------------

def _weekly_summary(storage) -> str:
    from src.config import local_now
    from datetime import timedelta
    end = local_now()
    start = end - timedelta(days=7)
    total = storage.get_total_spent(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    return f"Weekly spending (last 7 days): *S${total:.2f}*"


def _monthly_summary(storage) -> str:
    from src.config import local_now
    now = local_now()
    start = now.replace(day=1).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    total = storage.get_total_spent(start, end)
    return f"Monthly spending so far: *S${total:.2f}*"
