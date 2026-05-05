import asyncio
import calendar
import logging
import re
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ConversationHandler, ContextTypes, MessageHandler, filters

from src.categorizer import Categorizer
from src.config import local_now
from src.exchange import ExchangeRateService
from src.storage import Storage

logger = logging.getLogger(__name__)

EDIT_SELECT_FIELD = 0
EDIT_ENTER_VALUE = 1

SOURCE_LABELS: dict[str, str] = {
    "dbs_paylah":   "DBS PayLah!",
    "uob_paynow":   "UOB PayNow",
    "uob_card":     "UOB Card",
    "uob_transfer": "UOB Transfer",
    "apple_wallet": "Apple Wallet",
    "manual":       "Manual",
    "cash":         "Cash",
}


def _fmt_tx_date(transaction_date) -> str:
    """Return YYYY-MM-DD for midnight/bare dates, YYYY-MM-DD HH:MM for real times."""
    s = str(transaction_date or "")
    if not s:
        return "—"
    date_part = s[:10]
    time_part = s[11:16] if len(s) > 10 else ""
    if time_part and time_part != "00:00":
        return f"{date_part} {time_part}"
    return date_part


def get_category_keyboard(tx_id: int, categories: list[str]) -> InlineKeyboardMarkup:
    """Create a 2-column grid of category buttons for recategorization."""
    buttons = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(cat, callback_data=f"recat:{tx_id}:{cat}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


class _ReplyProxy:
    """Mimics a telegram.Message so handlers can call reply_text when the
    original callback message is inaccessible."""

    def __init__(self, bot, chat_id: int):
        self.bot = bot
        self.chat_id = chat_id

    async def reply_text(self, text: str, **kwargs):
        await self.bot.send_message(chat_id=self.chat_id, text=text, **kwargs)


def estimate_next_date(frequency: str, last_seen: str) -> str:
    """Estimate next occurrence date based on frequency."""
    last = datetime.strptime(last_seen[:10], "%Y-%m-%d")
    if frequency == "weekly":
        next_d = last + timedelta(weeks=1)
    elif frequency == "biweekly":
        next_d = last + timedelta(weeks=2)
    else:  # monthly
        next_month = last.month + 1 if last.month < 12 else 1
        next_year = last.year + 1 if last.month == 12 else last.year
        max_day = calendar.monthrange(next_year, next_month)[1]
        next_d = last.replace(year=next_year, month=next_month, day=min(last.day, max_day))
    return next_d.strftime("%d %b")


class TelegramBotService:
    def __init__(
        self,
        storage: Optional[Storage] = None,
        bot_token: str = "",
        categorizer: Optional[Categorizer] = None,
        exchange_service: Optional[ExchangeRateService] = None,
        dashboard_url: str = "",
        timezone: str = "Asia/Singapore",
        poller=None,
        oauth_redirect_uri: str = "",
        admin_storage=None,
    ):
        self.storage = storage
        self.admin_storage = admin_storage
        self.user_manager = None    # set via back-reference after UserManager is constructed
        self.bot_token = bot_token
        self.categorizer = categorizer
        self.exchange_service = exchange_service
        self.dashboard_url = dashboard_url
        self.timezone = timezone
        self.poller = poller
        self.oauth_redirect_uri = oauth_redirect_uri
        self.app = None
        self.chat_id: Optional[int] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Lifecycle state — read by /api/status
        self.is_running: bool = False
        self.last_error: Optional[str] = None
        # Restore persisted chat_id (single-user legacy mode only)
        if self.storage is not None:
            self._load_chat_id()

    def _resolve_chat_id(self, username: Optional[str] = None) -> Optional[int]:
        """Return the Telegram chat ID for a user (multi-user) or self.chat_id (legacy)."""
        if username and self.admin_storage:
            user = self.admin_storage.get_user(username)
            if user and user["telegram_chat_id"]:
                return int(user["telegram_chat_id"])
            return None
        return self.chat_id

    def _load_chat_id(self) -> None:
        if self.storage is None:
            return
        chat_id = self.storage.get_telegram_chat_id()
        if chat_id:
            self.chat_id = chat_id
            logger.info("Restored Telegram chat_id: %s", self.chat_id)

    def _save_chat_id(self, chat_id: int) -> None:
        if self.storage is not None:
            self.storage.set_telegram_chat_id(chat_id)

    def _get_chat_id(self, update) -> Optional[int]:
        """Extract chat_id from a real Update or the SimpleNamespace proxy used by _cmd_callback."""
        if hasattr(update, "effective_chat") and update.effective_chat:
            return update.effective_chat.id
        if hasattr(update, "message") and update.message and hasattr(update.message, "chat_id"):
            return update.message.chat_id
        return None

    async def _require_ctx(self, update):
        """Resolve UserContext for the calling chat.
        Multi-user mode: looks up via user_manager.get_by_chat_id().
        Legacy single-user mode (admin_storage is None): returns self so
          callers can use ctx.storage / ctx.categorizer transparently.
        Returns None (and sends an error reply) if the chat is not linked.
        """
        if self.admin_storage is None:
            # Legacy path — self.storage and self.categorizer are set directly
            return self
        chat_id = self._get_chat_id(update)
        ctx = self.user_manager.get_by_chat_id(chat_id) if (chat_id and self.user_manager) else None
        if ctx is None:
            try:
                await update.message.reply_text(
                    "Send `/start <code>` from the Cashe onboarding page to link your account.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass
        return ctx

    def _local_now(self) -> datetime:
        """Return current datetime in the configured local timezone."""
        return local_now(self.timezone)

    def parse_add_command(self, text: str) -> Optional[dict]:
        parts = text.strip().split()
        if len(parts) < 2:
            return None
        try:
            amount = float(parts[0])
        except ValueError:
            return None
        if amount <= 0:
            return None

        remaining = parts[1:]
        date = None
        category = None

        # Check last two tokens for "YYYY-MM-DD HH:MM" datetime
        if len(remaining) >= 3:
            try:
                datetime.strptime(f"{remaining[-2]} {remaining[-1]}", "%Y-%m-%d %H:%M")
                date = f"{remaining[-2]}T{remaining[-1]}:00"
                remaining = remaining[:-2]
            except ValueError:
                pass

        # Fall back: check last token for bare "YYYY-MM-DD" — store as midnight
        if date is None and len(remaining) >= 2:
            try:
                datetime.strptime(remaining[-1], "%Y-%m-%d")
                date = f"{remaining[-1]}T00:00:00"
                remaining = remaining[:-1]
            except ValueError:
                pass

        # Only extract category if a date was found — otherwise everything is the merchant
        if date is not None and len(remaining) >= 2:
            category = remaining[-1]
            merchant = " ".join(remaining[:-1])
        else:
            merchant = " ".join(remaining)

        return {
            "amount": amount,
            "merchant": merchant,
            "category": category,
            "date": date,
        }

    @staticmethod
    def _escape_md(text: str) -> str:
        """Strip Telegram Markdown special characters from user-provided text."""
        for ch in ("_", "*", "`", "["):
            text = text.replace(ch, "")
        return text

    def _format_tx_block(self, tx: dict, icon_map: dict[str, str] | None = None) -> str:
        if icon_map is None:
            icon_map = {}
        merchant  = self._escape_md(str(tx.get("merchant") or tx.get("description") or "Unknown"))
        category  = str(tx.get("category") or "Uncategorized")
        icon      = icon_map.get(category, "")
        cat_display = f"{icon} {self._escape_md(category)}" if icon else self._escape_md(category)
        amount    = float(tx.get("amount", 0))
        currency  = str(tx.get("currency", "SGD"))
        rate      = float(tx.get("exchange_rate") or 1.0)
        tx_date   = _fmt_tx_date(tx.get("transaction_date"))
        tx_id     = tx.get("id", "?")
        is_income = tx.get("type") == "income"
        raw_source = str(tx.get("source", "unknown"))
        if raw_source == "apple_wallet" and str(tx.get("description", "")).startswith("Apple Wallet"):
            source_label = self._escape_md(str(tx.get("description", "Apple Wallet")))
        else:
            source_label = self._escape_md(SOURCE_LABELS.get(raw_source, raw_source))

        row_prefix = "💰 " if is_income else ""
        amt_prefix = "+" if is_income else ""
        lines = [f"{row_prefix}*{merchant}* · {cat_display}"]
        if currency != "SGD" and rate != 1.0:
            sgd = amount * rate
            lines.append(f"`{amt_prefix}${sgd:.2f} SGD` `({currency} {amount:.2f})` · {source_label}")
        else:
            lines.append(f"`{amt_prefix}${amount:.2f} {currency}` · {source_label}")
        lines.append(f"_{tx_id} · {tx_date}_")
        return "\n".join(lines)

    async def _send_long_message(self, update: Update, text: str, parse_mode: str = "Markdown", reply_markup=None) -> None:
        limit = 3800

        async def _send(part: str, markup=None):
            try:
                await update.message.reply_text(part, parse_mode=parse_mode, reply_markup=markup)
            except Exception:
                await update.message.reply_text(part, reply_markup=markup)

        if len(text) <= limit:
            await _send(text, reply_markup)
            return
        parts = []
        while text:
            if len(text) <= limit:
                parts.append(text)
                break
            split_at = text.rfind("\n", 0, limit)
            if split_at == -1:
                split_at = limit
            parts.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        for i, part in enumerate(parts):
            markup = reply_markup if i == len(parts) - 1 else None
            await _send(part, markup)

    def _build_summary_with_transactions(self, header: str, summary: dict, start_date: str, end_date: str, storage=None) -> str:
        _storage = storage if storage is not None else self.storage
        icon_map = _storage.get_category_icon_map()
        lines = [header, f"Total: `${summary['total']:.2f}`", ""]
        for cat, total in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
            icon = icon_map.get(cat, "")
            prefix = f"{icon} " if icon else ""
            lines.append(f"{prefix}{self._escape_md(cat)}: `${total:.2f}`")

        transactions = _storage.query_transactions(start_date=start_date, end_date=end_date, limit=200)
        if transactions:
            lines.append("")
            lines.append("*Transactions:*")
            for tx in transactions:
                lines.append("─────────")
                lines.append(self._format_tx_block(tx, icon_map))

        return "\n".join(lines)

    def format_daily_summary(self, date: str, storage=None) -> str:
        _storage = storage if storage is not None else self.storage
        summary = _storage.get_spending_summary(start_date=date, end_date=date)
        if summary["total"] == 0:
            return f"No transactions on {date}"

        return self._build_summary_with_transactions(
            f"*Spending for {date}*", summary, date, date, storage=_storage
        )

    def format_weekly_summary(self, start_date: str, end_date: str, storage=None) -> str:
        _storage = storage if storage is not None else self.storage
        summary = _storage.get_spending_summary(start_date=start_date, end_date=end_date)
        if summary["total"] == 0:
            return "No transactions in this period"

        return self._build_summary_with_transactions(
            f"*Weekly Summary ({start_date} to {end_date})*", summary, start_date, end_date, storage=_storage
        )

    async def _delete_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: /delete <id>")
            return
        tx_id = int(args[0])
        tx = ctx.storage.get_transaction(tx_id)
        if not tx:
            await update.message.reply_text("Transaction not found.")
            return
        amount_sgd = tx["amount"] * tx.get("exchange_rate", 1.0)
        date_str = _fmt_tx_date(tx.get("transaction_date"))
        msg = (
            f"Delete this transaction?\n\n"
            f"*{tx.get('merchant', '—')}* — ${amount_sgd:.2f} SGD\n"
            f"Category: {tx.get('category', '—')}\n"
            f"Date: {date_str}\n"
            f"Source: {tx.get('source', '—')}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Confirm Delete", callback_data=f"confirm_delete_{tx_id}"),
            InlineKeyboardButton("Cancel", callback_data="cancel_delete"),
        ]])
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")

    async def _delete_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data
        if data == "cancel_delete":
            await query.edit_message_text("Cancelled.")
            return
        if data.startswith("confirm_delete_"):
            tx_id = int(data.split("_")[-1])
            ctx = await self._require_ctx(update)
            if ctx is None:
                await query.edit_message_text("Account not linked.")
                return
            try:
                ctx.storage.delete_transaction(tx_id)
                await query.edit_message_text(f"Transaction #{tx_id} deleted.")
            except ValueError:
                await query.edit_message_text("Transaction not found (may have already been deleted).")

    async def _edit_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return ConversationHandler.END
        args = context.args
        if not args or not args[0].isdigit():
            await update.message.reply_text("Usage: /edit <id>")
            return ConversationHandler.END
        tx_id = int(args[0])
        tx = ctx.storage.get_transaction(tx_id)
        if not tx:
            await update.message.reply_text("Transaction not found.")
            return ConversationHandler.END
        context.user_data["edit_tx_id"] = tx_id
        amount_sgd = tx["amount"] * tx.get("exchange_rate", 1.0)
        date_str = _fmt_tx_date(tx.get("transaction_date"))
        msg = (
            f"*Transaction #{tx_id}*\n"
            f"Merchant: {tx.get('merchant', '—')}\n"
            f"Amount: {tx.get('currency', 'SGD')} {tx['amount']:.2f} (SGD {amount_sgd:.2f})\n"
            f"Category: {tx.get('category', '—')}\n"
            f"Date: {date_str}\n"
            f"Description: {tx.get('description', '—')}\n\n"
            "What would you like to edit?"
        )
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Merchant", callback_data="ef_merchant"),
                InlineKeyboardButton("Amount", callback_data="ef_amount"),
            ],
            [
                InlineKeyboardButton("Category", callback_data="ef_category"),
                InlineKeyboardButton("Date", callback_data="ef_date"),
            ],
            [InlineKeyboardButton("Description", callback_data="ef_description")],
            [InlineKeyboardButton("Cancel", callback_data="ef_cancel")],
        ])
        await update.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
        return EDIT_SELECT_FIELD

    async def _edit_field_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()
        field = query.data  # e.g. "ef_merchant"

        if field == "ef_cancel":
            await query.edit_message_text("Edit cancelled.")
            context.user_data.clear()
            return ConversationHandler.END

        field_name = field.split("_", 1)[1]  # "merchant", "amount", etc.
        context.user_data["edit_field"] = field_name

        if field_name == "category":
            edit_ctx = await self._require_ctx(update)
            if edit_ctx is None:
                await query.edit_message_text("Account not linked.")
                context.user_data.clear()
                return ConversationHandler.END
            cats = edit_ctx.storage.get_categories()
            buttons = []
            row = []
            for i, cat in enumerate(cats):
                icon = cat.get("icon", "") or ""
                label = f"{icon} {cat['name']}".strip()
                row.append(InlineKeyboardButton(label, callback_data=f"ec_{cat['name']}"))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton("Cancel", callback_data="ef_cancel")])
            await query.edit_message_text("Select new category:", reply_markup=InlineKeyboardMarkup(buttons))
            return EDIT_SELECT_FIELD

        prompts = {
            "merchant": "Enter new merchant name:",
            "amount": "Enter new amount (numbers only, e.g. 12.50):",
            "date": "Enter new date (YYYY-MM-DD or DD/MM/YYYY):",
            "description": "Enter new description (or 'clear' to remove):",
        }
        await query.edit_message_text(prompts.get(field_name, "Enter value:"))
        return EDIT_ENTER_VALUE

    async def _edit_category_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        query = update.callback_query
        await query.answer()

        if query.data == "ef_cancel":
            await query.edit_message_text("Edit cancelled.")
            context.user_data.clear()
            return ConversationHandler.END

        category = query.data[3:]  # strip "ec_"
        tx_id = context.user_data.get("edit_tx_id")
        edit_ctx = await self._require_ctx(update)
        if edit_ctx is None:
            await query.edit_message_text("Account not linked.")
            context.user_data.clear()
            return ConversationHandler.END
        tx = edit_ctx.storage.get_transaction(tx_id)
        if not tx:
            await query.edit_message_text("Transaction no longer exists.")
            context.user_data.clear()
            return ConversationHandler.END

        edit_ctx.storage.update_transaction(tx_id, category=category)
        if tx.get("merchant") and edit_ctx.categorizer:
            edit_ctx.categorizer.learn_merchant(tx["merchant"], category, edit_ctx.storage)

        await query.edit_message_text(f"Category updated to *{category}*.", parse_mode="Markdown")
        context.user_data.clear()
        return ConversationHandler.END

    async def _edit_value_entered(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        tx_id = context.user_data.get("edit_tx_id")
        field = context.user_data.get("edit_field")
        text = update.message.text.strip()

        edit_ctx = await self._require_ctx(update)
        if edit_ctx is None:
            await update.message.reply_text("Account not linked.")
            context.user_data.clear()
            return ConversationHandler.END

        tx = edit_ctx.storage.get_transaction(tx_id)
        if not tx:
            await update.message.reply_text("Transaction no longer exists.")
            context.user_data.clear()
            return ConversationHandler.END

        if field == "amount":
            try:
                value = float(text.replace(",", ""))
            except ValueError:
                await update.message.reply_text("Invalid amount. Enter a number like 12.50:")
                return EDIT_ENTER_VALUE
            edit_ctx.storage.update_transaction(tx_id, amount=value)
            await update.message.reply_text(f"Amount updated to {value:.2f}.")

        elif field == "date":
            iso = None
            # Try YYYY-MM-DD
            try:
                datetime.strptime(text[:10], "%Y-%m-%d")
                iso = text[:10]
            except ValueError:
                pass
            # Try DD/MM/YYYY
            if iso is None and re.match(r"\d{2}/\d{2}/\d{4}", text):
                try:
                    d, m, y = text.split("/")
                    datetime.strptime(f"{y}-{m}-{d}", "%Y-%m-%d")
                    iso = f"{y}-{m}-{d}"
                except ValueError:
                    pass
            if iso is None:
                await update.message.reply_text("Invalid date. Use YYYY-MM-DD or DD/MM/YYYY:")
                return EDIT_ENTER_VALUE
            edit_ctx.storage.update_transaction(tx_id, transaction_date=f"{iso}T00:00:00")
            await update.message.reply_text(f"Date updated to {iso}.")

        elif field == "description":
            value = None if text.lower() == "clear" else text
            edit_ctx.storage.update_transaction(tx_id, description=value)
            await update.message.reply_text("Description updated." if value else "Description cleared.")

        elif field == "merchant":
            edit_ctx.storage.update_transaction(tx_id, merchant=text)
            await update.message.reply_text(f"Merchant updated to *{text}*.", parse_mode="Markdown")

        context.user_data.clear()
        return ConversationHandler.END

    def setup_handlers(self) -> None:
        async def _post_init(application: Application) -> None:
            await application.bot.set_my_commands([
                BotCommand("start",            "Initialize the bot"),
                BotCommand("today",            "Today's spending"),
                BotCommand("yesterday",        "Yesterday's spending"),
                BotCommand("week",             "This week's spending"),
                BotCommand("month",            "This month's breakdown"),
                BotCommand("add",              "Add an expense (supports multi-currency)"),
                BotCommand("cash",             "Quick cash expense entry"),
                BotCommand("income",           "Record income"),
                BotCommand("balance",          "Income vs expenses this month"),
                BotCommand("insights",         "Top merchants & daily average spend"),
                BotCommand("subscriptions",    "Detected recurring transactions"),
                BotCommand("recategorize",     "Reassign a transaction's category"),
                BotCommand("compare",          "This month vs last month"),
                BotCommand("merchants_report", "Top merchants this month"),
                BotCommand("velocity",         "Spending pace and projection"),
                BotCommand("summary",          "Monthly summary report"),
                BotCommand("dashboard",        "Open the web dashboard"),
                BotCommand("menu",             "Quick action buttons"),
                BotCommand("help",             "Show all commands"),
                BotCommand("delete",           "Delete a transaction"),
                BotCommand("edit",             "Edit a transaction field"),
                BotCommand("trip",             "Current trip summary (when trips active)"),
                BotCommand("reauth",           "Re-authorize Gmail access"),
                BotCommand("forcepoll",        "Force a Gmail poll for new emails"),
            ])
            await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

        self.app = Application.builder().token(self.bot_token).post_init(_post_init).build()

        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("today", self._today))
        self.app.add_handler(CommandHandler("week", self._week))
        self.app.add_handler(CommandHandler("month", self._month))
        self.app.add_handler(CommandHandler("add", self._add))
        self.app.add_handler(CommandHandler("cash", self._cash))
        self.app.add_handler(CommandHandler("recategorize", self._recategorize))
        self.app.add_handler(CommandHandler("income", self._income))
        self.app.add_handler(CommandHandler("balance", self._balance))
        self.app.add_handler(CommandHandler("insights", self._insights))
        self.app.add_handler(CommandHandler("subscriptions", self._subscriptions))
        self.app.add_handler(CommandHandler("help", self._help))
        self.app.add_handler(CommandHandler("dashboard", self._dashboard))
        self.app.add_handler(CommandHandler("compare", self._compare))
        self.app.add_handler(CommandHandler("merchants_report", self._merchants))
        self.app.add_handler(CommandHandler("velocity", self._velocity))
        self.app.add_handler(CommandHandler("summary", self._summary))
        self.app.add_handler(CommandHandler("yesterday", self._yesterday))
        self.app.add_handler(CommandHandler("menu", self._menu))

        self.app.add_handler(CallbackQueryHandler(self._cmd_callback, pattern="^cmd_"))
        self.app.add_handler(CallbackQueryHandler(self._category_callback, pattern="^cat:"))
        self.app.add_handler(CallbackQueryHandler(self._recat_callback, pattern="^recat:"))

        edit_conv = ConversationHandler(
            entry_points=[CommandHandler("edit", self._edit_start)],
            states={
                EDIT_SELECT_FIELD: [
                    CallbackQueryHandler(self._edit_category_selected, pattern=r"^ec_"),
                    CallbackQueryHandler(self._edit_field_selected, pattern=r"^ef_"),
                ],
                EDIT_ENTER_VALUE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self._edit_value_entered),
                ],
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            conversation_timeout=300,
        )
        self.app.add_handler(edit_conv)
        self.app.add_handler(CommandHandler("delete", self._delete_command))
        self.app.add_handler(CallbackQueryHandler(self._delete_callback, pattern=r"^(confirm_delete_\d+|cancel_delete)$"))
        self.app.add_handler(CommandHandler("trip", self._trip))
        self.app.add_handler(CommandHandler("reauth", self._reauth))
        self.app.add_handler(CommandHandler("forcepoll", self._forcepoll))

        # Catch-all must be last
        self.app.add_handler(MessageHandler(filters.COMMAND, self._unknown))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._unknown_text))

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        args = context.args or []

        # Multi-user mode: token-based linking
        if self.admin_storage is not None:
            if args:
                token = args[0]
                username = self.admin_storage.consume_telegram_link_token(token)
                if not username:
                    await update.message.reply_text(
                        "This code is invalid or has expired. "
                        "Return to the Cashe onboarding page to generate a new one."
                    )
                    return
                existing = self.admin_storage.get_user_by_chat_id(str(chat_id))
                if existing and existing["username"] != username:
                    await update.message.reply_text("This code belongs to a different account.")
                    return
                self.admin_storage.update_user(username, telegram_chat_id=str(chat_id))
                await update.message.reply_text("Your Telegram is now linked to Cashe.")
                return
            # /start with no args — check if already linked
            if self.user_manager:
                ctx = self.user_manager.get_by_chat_id(chat_id)
                if ctx:
                    await update.message.reply_text(
                        f"Welcome back! You're linked as *{ctx.username}*.",
                        parse_mode="Markdown",
                    )
                    return
            await update.message.reply_text(
                "Send `/start <code>` from the Cashe onboarding page to link your account.",
                parse_mode="Markdown",
            )
            return

        # Legacy single-user mode
        self.chat_id = chat_id
        self._save_chat_id(self.chat_id)
        await update.message.reply_text(
            "Expense Tracker bot ready! Use the menu button or /help to see all commands."
        )

    async def _today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        today = self._local_now().strftime("%Y-%m-%d")
        text = self.format_daily_summary(today, storage=ctx.storage)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Yesterday", callback_data="cmd_yesterday"),
                InlineKeyboardButton("📊 Week", callback_data="cmd_week"),
            ],
            [
                InlineKeyboardButton("➕ Add Cash", callback_data="cmd_cash"),
            ],
        ])
        await self._send_long_message(update, text, reply_markup=keyboard)

    async def _yesterday(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        yesterday = (self._local_now() - timedelta(days=1)).strftime("%Y-%m-%d")
        text = self.format_daily_summary(yesterday, storage=ctx.storage)
        await self._send_long_message(update, text)

    async def _week(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        today = self._local_now()
        start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        text = self.format_weekly_summary(start, end, storage=ctx.storage)
        await self._send_long_message(update, text)

    async def _month(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        today = self._local_now()
        start = f"{today.year}-{today.month:02d}-01"
        end = today.strftime("%Y-%m-%d")
        summary = ctx.storage.get_spending_summary(start_date=start, end_date=end)
        if summary["total"] == 0:
            await update.message.reply_text("No transactions this month")
            return
        text = self._build_summary_with_transactions(
            f"*Monthly Summary ({start} to {end})*", summary, start, end, storage=ctx.storage
        )
        await self._send_long_message(update, text)

    async def _add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        if not context.args:
            await update.message.reply_text("Usage: /add <amount> [currency] <merchant> [category] [date]")
            return
        text = " ".join(context.args)

        # Detect currency in the amount portion
        currency = "SGD"
        exchange_rate = 1.0
        amount_text = context.args[0]
        if self.exchange_service and len(context.args) >= 2:
            # Check if second arg is a currency code
            from src.exchange import CURRENCY_CODES
            if context.args[1].upper() in CURRENCY_CODES:
                currency = context.args[1].upper()
                amount_text = f"{context.args[0]} {context.args[1]}"
                # Rebuild text without currency for parse_add_command
                text = " ".join([context.args[0]] + list(context.args[2:]))
                exchange_rate = self.exchange_service.get_rate(currency)

        parsed = self.parse_add_command(text)
        if not parsed:
            await update.message.reply_text("Invalid format. Usage: /add <amount> [currency] <merchant> [category] [date]")
            return

        now = self._local_now()
        tx_date = parsed["date"] or now.strftime("%Y-%m-%dT%H:%M:%S")
        category = parsed["category"]
        if not category and ctx.categorizer:
            category, _ = ctx.categorizer.categorize(parsed["merchant"])

        tx_id = ctx.storage.insert_transaction(
            source="manual",
            source_id=f"manual-{now.strftime('%Y%m%d%H%M%S')}-{parsed['amount']}",
            amount=parsed["amount"],
            merchant=parsed["merchant"],
            category=category,
            currency=currency,
            exchange_rate=exchange_rate,
            transaction_date=tx_date,
        )
        ctx.storage.auto_assign_to_active_trip(tx_id)

        sgd_equivalent = parsed["amount"] * exchange_rate
        icon = ctx.storage.get_category_icon_map().get(category, "")
        cat_display = f"{icon} {self._escape_md(category)}" if icon else self._escape_md(category)
        msg = f"✅ *Added* #{tx_id}\n*{self._escape_md(parsed['merchant'])}* · {cat_display} · `${parsed['amount']:.2f} {currency}`"
        if currency != "SGD":
            msg += f"\n~ SGD `${sgd_equivalent:.2f}`"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        if not context.args:
            await update.message.reply_text(
                "Usage: /cash <amount> <merchant> [category] [date]\n"
                "Example: /cash 12.50 Toast Box food"
            )
            return
        text = " ".join(context.args)
        parsed = self.parse_add_command(text)
        if not parsed:
            # Distinguish between bad amount and missing merchant
            parts = text.strip().split()
            try:
                amount = float(parts[0])
            except (ValueError, IndexError):
                await update.message.reply_text("Invalid amount. Usage: /cash <amount> <merchant> [category] [date]")
                return
            if amount <= 0:
                await update.message.reply_text("Amount must be positive. Usage: /cash <amount> <merchant> [category] [date]")
                return
            await update.message.reply_text("Missing merchant. Usage: /cash <amount> <merchant> [category] [date]")
            return

        now = self._local_now()
        tx_date = parsed["date"] or now.strftime("%Y-%m-%dT%H:%M:%S")
        category = parsed["category"]
        if not category and ctx.categorizer:
            category, _ = ctx.categorizer.categorize(parsed["merchant"])

        tx_id = ctx.storage.insert_transaction(
            source="cash",
            source_id=f"cash-{now.strftime('%Y%m%d%H%M%S')}-{parsed['amount']}",
            amount=parsed["amount"],
            merchant=parsed["merchant"],
            category=category,
            transaction_date=tx_date,
        )
        ctx.storage.auto_assign_to_active_trip(tx_id)
        icon = ctx.storage.get_category_icon_map().get(category, "")
        cat_display = f"{icon} {self._escape_md(category)}" if icon else self._escape_md(category)
        msg = f"✅ *Cash* #{tx_id}\n*{self._escape_md(parsed['merchant'])}* · {cat_display} · `${parsed['amount']:.2f} SGD`"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _recategorize(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        if not context.args:
            await update.message.reply_text("Usage: /recategorize <transaction_id>")
            return
        try:
            tx_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Transaction ID must be a number")
            return

        tx = ctx.storage.get_transaction(tx_id)
        if not tx:
            await update.message.reply_text(f"Transaction #{tx_id} not found")
            return

        # If a category was provided, apply it directly
        if len(context.args) >= 2:
            new_category = context.args[1]
            valid_categories = [c["name"] for c in ctx.storage.get_categories()]
            if new_category not in valid_categories:
                await update.message.reply_text(
                    f"Invalid category '{new_category}'. Valid: {', '.join(valid_categories)}"
                )
                return

            old_category = tx["category"]
            ctx.storage.update_transaction(tx_id, category=new_category)

            merchant = tx["merchant"]
            if merchant and ctx.categorizer:
                ctx.categorizer.learn_merchant(merchant, new_category, ctx.storage)
            elif merchant:
                ctx.storage.set_merchant_override(merchant, new_category)

            await update.message.reply_text(
                f"Updated #{tx_id}: {old_category} -> {new_category}"
                + (f" (learned: {merchant} = {new_category})" if merchant else "")
            )
            return

        # No category provided — show a grid of category buttons
        categories = ctx.storage.get_categories()
        keyboard = get_category_keyboard(tx_id, [c["name"] for c in categories])
        merchant = tx["merchant"] or "Unknown"
        current_category = tx["category"] or "Other"
        await update.message.reply_text(
            f"Recategorize #{tx_id}: {merchant} (currently {current_category})",
            reply_markup=keyboard,
        )

    async def _income(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        if not context.args:
            await update.message.reply_text(
                "Usage: /income <amount> <description> [date]\nExample: /income 5000 salary"
            )
            return

        try:
            amount = float(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid amount. Usage: /income <amount> <description> [date]")
            return

        if amount <= 0:
            await update.message.reply_text("Amount must be positive.")
            return

        remaining = list(context.args[1:])
        tx_date = None

        # Check last two tokens for "YYYY-MM-DD HH:MM"
        if len(remaining) >= 2:
            try:
                datetime.strptime(f"{remaining[-2]} {remaining[-1]}", "%Y-%m-%d %H:%M")
                tx_date = f"{remaining[-2]}T{remaining[-1]}:00"
                remaining = remaining[:-2]
            except ValueError:
                pass

        # Fall back: bare "YYYY-MM-DD" → midnight
        if tx_date is None and remaining:
            try:
                datetime.strptime(remaining[-1], "%Y-%m-%d")
                tx_date = f"{remaining[-1]}T00:00:00"
                remaining = remaining[:-1]
            except ValueError:
                pass

        description = " ".join(remaining) if remaining else "Income"
        now = self._local_now()
        date_str = tx_date or now.strftime("%Y-%m-%dT%H:%M:%S")

        tx_id = ctx.storage.insert_transaction(
            source="manual",
            source_id=f"manual-{now.strftime('%Y%m%d%H%M%S')}-{amount}",
            amount=amount,
            merchant=description,
            category="Income",
            transaction_date=date_str,
            tx_type="income",
        )

        msg = f"💰 *Income* #{tx_id}\n*{self._escape_md(description)}* · `${amount:.2f} SGD`"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        today = self._local_now()
        start = f"{today.year}-{today.month:02d}-01"
        end = today.strftime("%Y-%m-%d")
        balance = ctx.storage.get_balance(start, end)

        if balance["income"] == 0 and balance["expenses"] == 0:
            await update.message.reply_text("No transactions this month")
            return

        month_str = today.strftime("%B %Y")
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        days_remaining = days_in_month - today.day

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📊 Insights", callback_data="cmd_insights"),
            InlineKeyboardButton("🏠 Menu", callback_data="cmd_menu"),
        ]])

        await update.message.reply_text(
            f"*Balance for {month_str}*\n\n"
            f"💸 Income: *${balance['income']:.2f}*\n"
            f"💵 Expenses: *${balance['expenses']:.2f}*\n"
            f"💳 Net: *${balance['net']:.2f}*\n\n"
            f"_{days_remaining} days remaining this month_",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    async def _insights(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        today = self._local_now()
        start = f"{today.year}-{today.month:02d}-01"
        end = today.strftime("%Y-%m-%d")

        summary = ctx.storage.get_spending_summary(start, end)
        ranking = ctx.storage.get_merchant_ranking(start, end, limit=5)
        avg = ctx.storage.get_average_daily(start, end)

        if not summary["by_category"]:
            await update.message.reply_text("No spending data this month.")
            return

        lines = ["*Insights This Month*", ""]
        for cat, total in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"  {self._escape_md(cat)}: *${total:.2f}*")
        lines.append("")
        lines.append(f"*Daily average:* ${avg:.2f}")
        lines.append("")
        if ranking:
            lines.append("*Top Merchants*")
            for i, r in enumerate(ranking[:3], 1):
                lines.append(f"  {i}. {self._escape_md(r['merchant'])} — ${r['total']:.2f}")

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📊 Compare", callback_data="cmd_compare"),
            InlineKeyboardButton("🏠 Menu", callback_data="cmd_menu"),
        ]])

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=keyboard)

    async def _subscriptions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        rows = ctx.storage.get_recurring_transactions()
        if not rows:
            await update.message.reply_text("No recurring transactions detected yet.")
            return

        lines = ["*Recurring Transactions*"]
        for r in rows:
            freq = r["frequency"]
            amount = r["avg_amount"]
            merchant = r["merchant"]
            last_seen = r["last_seen"]
            if freq == "monthly":
                monthly_eq = amount
            elif freq == "weekly":
                monthly_eq = amount * 4.33
            elif freq == "biweekly":
                monthly_eq = amount * 2.17
            else:
                monthly_eq = amount
                logger.warning("Unknown recurring frequency %r for merchant %r", freq, merchant)
            next_date = estimate_next_date(freq, last_seen)
            lines.append(
                f"🔄 *{merchant}*\n"
                f"  ${amount:.2f} · {freq}\n"
                f"  Next: {next_date} · ~${monthly_eq:.2f}/mo"
            )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _compare(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Compare this month vs last month."""
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        result = ctx.storage.comparison(period="month")
        overall = result["overall"]
        categories = result["categories"]

        lines = ["*This Month vs Last Month*\n"]
        if overall["previous_total"] > 0 and overall["change_percent"] is not None:
            arrow = "\u2191" if overall["change"] > 0 else "\u2193"
            lines.append(
                f"*Overall:* ${overall['current_total']:.2f} {arrow} ${abs(overall['change']):.2f} "
                f"({overall['change_percent']:+.1f}%)\n"
            )
        else:
            lines.append(f"*Overall:* ${overall['current_total']:.2f} (no prior data)\n")

        for cat in categories[:5]:
            arrow = "\u2191" if cat["change"] > 0 else "\u2193"
            lines.append(
                f"{cat['category']}: ${cat['current']:.2f} {arrow} ${abs(cat['change']):.2f}"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _merchants(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show top 5 merchants this month."""
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        merchants = ctx.storage.top_merchants_by_period(limit=5)

        if not merchants:
            await update.message.reply_text("No merchant data this month.")
            return

        lines = ["*Top Merchants This Month*\n"]
        for i, m in enumerate(merchants, 1):
            lines.append(
                f"{i}. *{self._escape_md(m['merchant'])}* \u2014 ${m['total']:.2f} ({m['count']}x)"
            )

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _velocity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show spending velocity vs last month."""
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        v = ctx.storage.spending_velocity()

        emoji = "\u26a0" if v["status"] == "ahead" else "\u2705"
        lines = [
            f"{emoji} *Spending Velocity*\n",
            f"Spent MTD: *${v['current_mtd']:.2f}*",
            f"Last month: ${v['last_month_total']:.2f}",
            f"Projected: ${v['projected_total']:.2f}",
            f"Pace: {v['pace_percent']:.0f}% of last month",
        ]

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Generate on-demand monthly summary report."""
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        report = ctx.storage.generate_digest(report_type="monthly")

        arrow = "\u2191" if report["change"] > 0 else "\u2193"

        lines = [
            "*Monthly Summary*\n",
            f"*Total spent:* ${report['total_spent']:.2f} ({report['transaction_count']} transactions)",
        ]

        if report["top_category"]:
            lines.append(f"*Top category:* {report['top_category']['category']} (${report['top_category']['total']:.2f})")

        if report["biggest_transaction"]:
            bt = report["biggest_transaction"]
            lines.append(f"*Biggest:* {bt['merchant']} \u2014 ${bt['amount']:.2f}")

        if report["previous_total"] > 0 and report["change_percent"] is not None:
            lines.append(f"*vs last month:* {arrow} ${abs(report['change']):.2f} ({report['change_percent']:+.1f}%)")

        if report["new_merchant_count"] > 0:
            lines.append(f"*New merchants:* {report['new_merchant_count']}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _trip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ctx = await self._require_ctx(update)
        if ctx is None:
            return
        if ctx.storage.get_setting("trips_enabled", "false") != "true":
            await update.message.reply_text("Trips are not enabled. Enable in the dashboard Settings.")
            return

        active = ctx.storage.get_active_trip()
        if not active:
            await update.message.reply_text("No active trip. Activate one from the dashboard.")
            return

        summary = ctx.storage.get_trip_summary(active["id"])
        if not summary:
            await update.message.reply_text("Could not load trip summary.")
            return

        from datetime import datetime as _dt
        start_dt = _dt.strptime(active["start_date"], "%Y-%m-%d")
        now = self._local_now()
        days_elapsed = (now.date() - start_dt.date()).days + 1

        # Today's spend
        today_str = now.strftime("%Y-%m-%d")
        today_entry = next(
            (d for d in summary["by_day"] if d["date"] == today_str), None
        )
        today_amount = today_entry["amount_sgd"] if today_entry else 0.0

        dest = f" · {self._escape_md(active['destination'])}" if active.get("destination") else ""
        lines = [
            f"✈️ *{self._escape_md(active['name'])}*{dest} (Day {days_elapsed})",
        ]
        lines += [
            self._escape_md(f"Total: S${summary['total_sgd']:.2f} across {summary['transaction_count']} transactions"),
            self._escape_md(f"Daily avg: S${summary['daily_average_sgd']:.2f}"),
            self._escape_md(f"Today: S${today_amount:.2f}"),
        ]
        if summary["by_category"]:
            lines.append(self._escape_md("\nTop categories:"))
            for cat in summary["by_category"][:3]:
                lines.append(self._escape_md(f"  {cat['category']}: S${cat['amount_sgd']:.2f}"))

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        lines = [
            "*Expense Tracker Commands*\n",
            "📋 *Viewing*",
            "  /today — Today's spending",
            "  /week — This week's spending",
            "  /month — This month's spending",
            "  /balance — Income vs expenses",
            "  /insights — Category breakdown + top merchants",
            "  /subscriptions — Recurring transactions",
            "",
            "📊 *Analytics*",
            "  /compare — This month vs last month",
            "  /merchants_report — Top merchants by spend",
            "  /velocity — Spending pace analysis",
            "  /summary — Monthly summary report",
            "",
            "➕ *Adding*",
            "  /add \\[amount] \\[merchant] — Add expense",
            "  /cash \\[amount] \\[merchant] — Add cash expense",
            "  /income \\[amount] \\[desc] — Add income",
            "",
            "⚙ *Management*",
            "  /recategorize — Change transaction category",
            "  /delete <id> — Delete a transaction",
            "  /edit <id> — Edit a transaction field",
            "  /menu — Quick action buttons",
        ]
        text = "\n".join(lines)
        try:
            await update.message.reply_text(text, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(text)

    async def _dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.dashboard_url:
            await update.message.reply_text(f"Open dashboard: {self.dashboard_url}")
        else:
            await update.message.reply_text("Dashboard URL not configured.")

    async def _unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text or ""
        cmd = text.split()[0]
        await update.message.reply_text(
            f"Unknown command: {cmd}\n\n"
            "Available commands:\n"
            "/today /week /month — view spending\n"
            "/balance — income vs expenses\n"
            "/dashboard — open web dashboard\n"
            "/add — manual entry\n"
            "/cash — quick cash entry\n"
            "/income — record income\n"
            "/recategorize — change category\n"
            "/insights — spending patterns\n"
            "/subscriptions — recurring transactions\n"
            "/help — full command reference"
        )

    async def _unknown_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "I understand commands starting with /.\n"
            "Type /help for a full list."
        )

    def notify_text(self, text: str, username: Optional[str] = None) -> None:
        """Send a plain text message. Called from background threads (e.g., APScheduler)."""
        chat_id = self._resolve_chat_id(username)
        if not chat_id:
            logger.info("Cannot send notification: no chat_id registered (user must send /start)")
            return
        if not self._loop or not self.app:
            logger.debug("Cannot send text: bot not started yet")
            return
        fut = asyncio.run_coroutine_threadsafe(
            self.app.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown"),
            self._loop,
        )
        fut.add_done_callback(
            lambda f: logger.error("notify_text send failed: %s", f.exception()) if f.exception() else None
        )

    def notify_transaction(self, tx_id: int, amount: float, merchant: str, category: Optional[str], match_source: str, source: str, username: Optional[str] = None) -> None:
        """Send a transaction notification. Called from the Gmail poller thread."""
        chat_id = self._resolve_chat_id(username)
        if not chat_id:
            logger.info("Cannot send notification: no chat_id registered (user must send /start)")
            return
        if not self._loop or not self.app:
            logger.debug("Cannot notify: bot not started yet")
            return
        # Resolve the correct storage for this notification
        storage = self.storage
        if username and self.user_manager:
            ctx = self.user_manager.get(username)
            if ctx:
                storage = ctx.storage
        fut = asyncio.run_coroutine_threadsafe(
            self._async_notify(tx_id, amount, merchant, category, match_source, source, chat_id, storage),
            self._loop,
        )
        fut.add_done_callback(
            lambda f: logger.error("notify_transaction send failed: %s", f.exception()) if f.exception() else None
        )

    async def _async_notify(self, tx_id: int, amount: float, merchant: str, category: Optional[str], match_source: str, source: str, chat_id: Optional[int] = None, storage=None) -> None:
        _chat_id = chat_id if chat_id is not None else self.chat_id
        _storage = storage if storage is not None else self.storage
        icon_map = _storage.get_category_icon_map()
        tx = _storage.get_transaction(tx_id)
        # For Apple Wallet, show the card name stored in description
        if source == "apple_wallet":
            _desc = (tx.get("description") or "") if tx else ""
            source_label = _desc if _desc.startswith("Apple Wallet") else SOURCE_LABELS.get(source, source)
        else:
            source_label = SOURCE_LABELS.get(source, source)

        if tx and tx.get("type") == "income":
            # Income/credit: distinct "Received" notification, no category picker
            currency = str(tx.get("currency", "SGD"))
            rate = float(tx.get("exchange_rate") or 1.0)
            tx_date = _fmt_tx_date(tx.get("transaction_date"))
            lines = [f"💰 *Received* · {self._escape_md(merchant)}"]
            if currency != "SGD" and rate != 1.0:
                sgd = amount * rate
                lines.append(f"`+${sgd:.2f} SGD` `({currency} {amount:.2f})` · {self._escape_md(source_label)}")
            else:
                lines.append(f"`+${amount:.2f} {currency}` · {self._escape_md(source_label)}")
            lines.append(f"_{tx_id} · {tx_date}_")
            await self.app.bot.send_message(chat_id=_chat_id, text="\n".join(lines), parse_mode="Markdown")
        elif category and match_source != "default":
            text = self._format_tx_block(tx, icon_map)
            # Append trip context if trips are active
            if _storage.get_setting("trips_enabled", "false") == "true":
                active_trip = _storage.get_active_trip()
                if active_trip:
                    summary = _storage.get_trip_summary(active_trip["id"])
                    if summary:
                        from datetime import datetime as _dt
                        start_dt = _dt.strptime(active_trip["start_date"], "%Y-%m-%d")
                        day_num = (self._local_now().date() - start_dt.date()).days + 1
                        text += f"\n\n✈️ {active_trip['name']} · Trip total: S${summary['total_sgd']:.2f} (Day {day_num})"
            await self.app.bot.send_message(chat_id=_chat_id, text=text, parse_mode="Markdown")
        else:
            categories = _storage.get_categories()
            buttons = []
            row = []
            for cat in categories:
                row.append(InlineKeyboardButton(
                    f"{cat['icon']} {cat['name']}",
                    callback_data=f"cat:{tx_id}:{cat['name']}",
                ))
                if len(row) == 2:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            keyboard = InlineKeyboardMarkup(buttons)
            text = f"💸 *${amount:.2f}* at *{self._escape_md(merchant)}*\n{self._escape_md(source_label)} · Pick a category:"
            await self.app.bot.send_message(
                chat_id=_chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

        # Budget alert check — income transactions don't trigger budget alerts
        if tx and tx.get("type") != "income":
            try:
                _sgd = tx["amount"] * (tx.get("exchange_rate") or 1.0)
                await self._check_and_alert_budgets(category, _sgd, _storage, chat_id=_chat_id)
            except Exception as _e:
                logger.warning("Budget alert check failed: %s", _e)

    async def _check_and_alert_budgets(
        self, category: Optional[str], amount_sgd: float, storage=None, chat_id: Optional[int] = None
    ) -> None:
        """Check budget thresholds and send alerts if a 80% or 100% boundary was just crossed.

        Called at the end of _async_notify after every ingested transaction.
        """
        _storage = storage if storage is not None else self.storage
        if _storage.get_setting("budgets_enabled", "false") != "true":
            return
        _chat_id = chat_id if chat_id is not None else self.chat_id
        if not _chat_id or not self.app:
            return

        progress = _storage.get_budget_progress()
        for b in progress:
            # Only check the overall budget and the budget matching this transaction's category
            is_overall = b["category"] is None
            is_matching = b["category"] == category
            if not is_overall and not is_matching:
                continue

            current_pct = b["percent"]
            prior_spent = b["spent"] - amount_sgd
            prior_pct = (
                round(prior_spent / b["budget_amount"] * 100, 1)
                if b["budget_amount"] > 0
                else 0.0
            )

            # Derive current from prior + new amount in case tx not yet in DB
            current_spent = b["spent"] + amount_sgd
            current_pct_calc = (
                round(current_spent / b["budget_amount"] * 100, 1)
                if b["budget_amount"] > 0
                else 0.0
            )
            # Use whichever current is higher (covers both: tx in DB or not yet)
            effective_current = max(current_pct, current_pct_calc)
            effective_prior = min(prior_pct, b["percent"])

            label = b["label"]
            period_word = "month" if b["period"] == "monthly" else "week"

            if effective_prior < 100 <= effective_current:
                display_spent = max(b["spent"], current_spent)
                overage = display_spent - b["budget_amount"]
                msg = (
                    f"🚨 *Budget Exceeded — {label}*\n"
                    f"You've spent ${display_spent:.2f} of your ${b['budget_amount']:.2f} "
                    f"{b['period']} budget.\n"
                    f"${overage:.2f} over budget this {period_word}."
                )
                await self.app.bot.send_message(
                    chat_id=_chat_id, text=msg, parse_mode="Markdown"
                )
            elif effective_prior < 80 <= effective_current < 100:
                display_spent = max(b["spent"], current_spent)
                display_remaining = b["budget_amount"] - display_spent
                msg = (
                    f"⚠️ *Budget Alert — {label}*\n"
                    f"You've spent ${display_spent:.2f} of your ${b['budget_amount']:.2f} "
                    f"{b['period']} budget ({effective_current:.0f}%).\n"
                    f"${display_remaining:.2f} remaining for the rest of the {period_word}."
                )
                await self.app.bot.send_message(
                    chat_id=_chat_id, text=msg, parse_mode="Markdown"
                )

    async def _apply_category_update(self, tx_id: int, category: str, query, storage=None, categorizer=None) -> None:
        """Shared body for cat: and recat: callbacks — update category, learn override, refresh message."""
        _storage = storage if storage is not None else self.storage
        _categorizer = categorizer if categorizer is not None else self.categorizer
        tx = _storage.get_transaction(tx_id)
        if not tx:
            await query.edit_message_text("Transaction not found.")
            return
        _storage.update_transaction(tx_id, category=category)
        merchant = tx["merchant"]
        if merchant and _categorizer:
            _categorizer.learn_merchant(merchant, category, _storage)
        elif merchant:
            _storage.set_merchant_override(merchant, category)
        icon_map = _storage.get_category_icon_map()
        updated_tx = _storage.get_transaction(tx_id)
        await query.edit_message_text(
            self._format_tx_block(updated_tx, icon_map),
            parse_mode="Markdown",
        )

    async def _category_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        if not query.data.startswith("cat:"):
            return
        _, tx_id_str, category = query.data.split(":", 2)
        cb_ctx = await self._require_ctx(update)
        storage = cb_ctx.storage if cb_ctx else None
        categorizer = cb_ctx.categorizer if cb_ctx else None
        await self._apply_category_update(int(tx_id_str), category, query, storage=storage, categorizer=categorizer)

    async def _recat_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        if not query.data.startswith("recat:"):
            return
        _, tx_id_str, category = query.data.split(":", 2)
        cb_ctx = await self._require_ctx(update)
        storage = cb_ctx.storage if cb_ctx else None
        categorizer = cb_ctx.categorizer if cb_ctx else None
        await self._apply_category_update(int(tx_id_str), category, query, storage=storage, categorizer=categorizer)

    async def _cmd_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data

        if not data or not data.startswith("cmd_"):
            return

        handler_map = {
            "cmd_today": self._today,
            "cmd_yesterday": self._yesterday,
            "cmd_week": self._week,
            "cmd_insights": self._insights,
            "cmd_balance": self._balance,
            "cmd_compare": self._compare,
            "cmd_merchants": self._merchants,
            "cmd_velocity": self._velocity,
            "cmd_summary": self._summary,
            "cmd_menu": self._menu,
            "cmd_cash": self._cash,
            "cmd_subscriptions": self._subscriptions,
            "cmd_add": self._add,
            "cmd_income": self._income,
        }

        handler = handler_map.get(data)
        if not handler:
            return

        # Update is frozen in python-telegram-bot v21+ — build a lightweight
        # stand-in with a .message that supports reply_text via bot.send_message.
        chat_id = (
            query.message.chat_id
            if query.message and hasattr(query.message, "chat_id")
            else (self.chat_id or query.from_user.id)
        )
        proxy_update = SimpleNamespace(message=_ReplyProxy(context.bot, chat_id))
        try:
            await handler(proxy_update, context)
        except Exception as e:
            logger.error("Error handling callback %s: %s", data, e, exc_info=True)
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Something went wrong processing that action. Try the command directly instead.",
                )
            except Exception:
                pass

    async def _menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📅 Today", callback_data="cmd_today"),
                InlineKeyboardButton("📆 Week", callback_data="cmd_week"),
            ],
            [
                InlineKeyboardButton("📊 Insights", callback_data="cmd_insights"),
                InlineKeyboardButton("📋 Balance", callback_data="cmd_balance"),
            ],
            [
                InlineKeyboardButton("🔄 Subscriptions", callback_data="cmd_subscriptions"),
                InlineKeyboardButton("📈 Compare", callback_data="cmd_compare"),
            ],
            [
                InlineKeyboardButton("➕ Add", callback_data="cmd_add"),
                InlineKeyboardButton("💰 Income", callback_data="cmd_income"),
            ],
        ])
        await update.message.reply_text(
            "*Quick Actions*",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    async def _send_daily_digest(self, chat_id: Optional[int] = None, storage=None) -> None:
        """Send morning digest: yesterday's total, month-to-date, any alerts."""
        _chat_id = chat_id if chat_id is not None else self.chat_id
        _storage = storage if storage is not None else self.storage
        if not _chat_id:
            logger.debug("Cannot send daily digest: no chat_id")
            return

        _now = self._local_now()
        yesterday = (_now - timedelta(days=1)).strftime("%Y-%m-%d")
        today = _now.strftime("%Y-%m-%d")

        # Yesterday's total — use get_spending_summary to handle NULL-type rows correctly
        yesterday_summary = _storage.get_spending_summary(yesterday, yesterday)
        yesterday_total = yesterday_summary["total"]
        yesterday_count = len(_storage.query_transactions(start_date=yesterday, end_date=yesterday, limit=10_000))

        # Month to date
        month_start = _now.replace(day=1).strftime("%Y-%m-%d")
        month_total = _storage.get_spending_summary(month_start, today)["total"]

        # Velocity, new merchants, anomalies
        velocity = _storage.spending_velocity()
        new_merchants_list = _storage.new_merchants()
        anomaly_multiplier = float(_storage.get_setting("anomaly_multiplier", "2.0"))
        anomalies = _storage.spending_anomalies(multiplier=anomaly_multiplier)

        lines = [
            "*Morning Digest*\n",
            f"Yesterday: *${yesterday_total:.2f}* ({yesterday_count} transactions)",
            f"Month to date: *${month_total:.2f}*\n",
        ]

        velocity_threshold = float(_storage.get_setting("velocity_alert_threshold", "110"))
        if velocity["pace_percent"] > velocity_threshold:
            lines.append(f"⚠ Spending {velocity['pace_percent']:.0f}% of last month's pace")

        if new_merchants_list:
            lines.append(f"🛍 {len(new_merchants_list)} new merchant(s)")

        if anomalies:
            lines.append(f"⚠ {len(anomalies)} unusual transaction(s)")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Insights", callback_data="cmd_insights"),
                InlineKeyboardButton("📋 Balance", callback_data="cmd_balance"),
            ],
        ])

        await self.app.bot.send_message(
            chat_id=_chat_id,
            text="\n".join(lines),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    def _resolve_poller(self, update):
        """Return the GmailPoller for the sending user (multi-user) or self.poller (legacy)."""
        if self.user_manager:
            chat_id = self._get_chat_id(update)
            ctx = self.user_manager.get_by_chat_id(chat_id) if chat_id else None
            return ctx.poller if ctx else None
        return self.poller

    async def _reauth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        poller = self._resolve_poller(update)
        if not poller or not self.oauth_redirect_uri:
            await update.message.reply_text("Gmail not configured.")
            return
        try:
            auth_url = poller.start_reauth(self.oauth_redirect_uri)
            await update.message.reply_text(
                f"Click the link below to re-authorize Gmail:\n{auth_url}",
                disable_web_page_preview=True,
            )
        except Exception as e:
            await update.message.reply_text(f"Failed to start re-authorization: {e}")

    async def _forcepoll(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        poller = self._resolve_poller(update)
        if not poller:
            await update.message.reply_text("Gmail not configured.")
            return
        if not poller.service:
            await update.message.reply_text("Gmail not authenticated. Use /reauth first.")
            return
        await update.message.reply_text("Polling Gmail for new emails...")
        try:
            count = poller.force_poll()
            if count == 0:
                await update.message.reply_text("No new transactions found.")
            else:
                await update.message.reply_text(f"Ingested {count} new transaction(s).")
        except Exception as e:
            await update.message.reply_text(f"Poll failed: {e}")

    def notify_daily_digest(self, username: Optional[str] = None) -> None:
        """Schedule daily digest send. Called from APScheduler background thread."""
        chat_id = self._resolve_chat_id(username)
        if not chat_id:
            logger.info("Cannot send daily digest: no chat_id registered (user must send /start)")
            return
        if not self._loop or not self.app:
            logger.debug("Cannot send daily digest: bot not started")
            return
        # Resolve per-user storage if in multi-user mode
        storage = self.storage
        if username and self.user_manager:
            ctx = self.user_manager.get(username)
            if ctx:
                storage = ctx.storage
        if storage is None:
            logger.warning("Cannot send daily digest: no storage resolved for user %r", username)
            return
        fut = asyncio.run_coroutine_threadsafe(
            self._send_daily_digest(chat_id=chat_id, storage=storage),
            self._loop,
        )
        fut.add_done_callback(
            lambda f: logger.error("notify_daily_digest send failed: %s", f.exception()) if f.exception() else None
        )
