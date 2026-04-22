import asyncio
import calendar
import logging
import re
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from src.analytics import (
    get_period_comparison,
    get_category_comparison,
    get_top_merchants,
    get_spending_velocity,
    generate_summary,
    get_anomalies,
    check_new_merchants,
)
from src.categorizer import Categorizer
from src.exchange import ExchangeRateService
from src.storage import Storage

logger = logging.getLogger(__name__)

SOURCE_LABELS: dict[str, str] = {
    "dbs_paylah":   "DBS PayLah!",
    "uob_paynow":   "UOB PayNow",
    "uob_card":     "UOB Card",
    "apple_wallet": "Apple Wallet",
    "manual":       "Manual",
    "cash":         "Cash",
}


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
    def __init__(self, storage: Storage, bot_token: str, categorizer: Optional[Categorizer] = None, exchange_service: Optional[ExchangeRateService] = None, dashboard_url: str = ""):
        self.storage = storage
        self.bot_token = bot_token
        self.categorizer = categorizer
        self.exchange_service = exchange_service
        self.dashboard_url = dashboard_url
        self.app = None
        self.chat_id: Optional[int] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Restore persisted chat_id
        self._load_chat_id()

    def _load_chat_id(self) -> None:
        row = self.storage.conn.execute(
            "SELECT last_processed_id FROM ingestion_state WHERE source = 'telegram_chat_id'"
        ).fetchone()
        if row and row["last_processed_id"]:
            self.chat_id = int(row["last_processed_id"])
            logger.info("Restored Telegram chat_id: %s", self.chat_id)

    def _save_chat_id(self, chat_id: int) -> None:
        self.storage.conn.execute(
            """INSERT OR REPLACE INTO ingestion_state (source, last_processed_id, last_processed_at, updated_at)
               VALUES ('telegram_chat_id', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (str(chat_id),),
        )
        self.storage.conn.commit()

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

        # Check if the last token is a valid date
        if len(remaining) >= 2:
            try:
                datetime.strptime(remaining[-1], "%Y-%m-%d")
                date = remaining[-1]
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
        """Escape Telegram Markdown special characters in user-provided text."""
        for ch in ("_", "*", "`", "["):
            text = text.replace(ch, f"\\{ch}")
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
        tx_date   = str(tx.get("transaction_date", ""))[:10]
        tx_id     = tx.get("id", "?")
        raw_source = str(tx.get("source", "unknown"))
        source_label = self._escape_md(SOURCE_LABELS.get(raw_source, raw_source))

        lines = [f"*{merchant}* · {cat_display}"]
        if currency != "SGD" and rate != 1.0:
            sgd = amount * rate
            lines.append(f"`${sgd:.2f} SGD` `({currency} {amount:.2f})` · {source_label}")
        else:
            lines.append(f"`${amount:.2f} {currency}` · {source_label}")
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

    def _build_summary_with_transactions(self, header: str, summary: dict, start_date: str, end_date: str) -> str:
        icon_map = self.storage.get_category_icon_map()
        lines = [header, f"Total: `${summary['total']:.2f}`", ""]
        for cat, total in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
            icon = icon_map.get(cat, "")
            prefix = f"{icon} " if icon else ""
            lines.append(f"{prefix}{self._escape_md(cat)}: `${total:.2f}`")

        transactions = self.storage.query_transactions(start_date=start_date, end_date=end_date, limit=200)
        if transactions:
            lines.append("")
            lines.append("*Transactions:*")
            for tx in transactions:
                lines.append("─────────")
                lines.append(self._format_tx_block(tx, icon_map))

        return "\n".join(lines)

    def format_daily_summary(self, date: str) -> str:
        summary = self.storage.get_spending_summary(start_date=date, end_date=date)
        if summary["total"] == 0:
            return f"No transactions on {date}"

        return self._build_summary_with_transactions(
            f"*Spending for {date}*", summary, date, date
        )

    def format_weekly_summary(self, start_date: str, end_date: str) -> str:
        summary = self.storage.get_spending_summary(start_date=start_date, end_date=end_date)
        if summary["total"] == 0:
            return "No transactions in this period"

        return self._build_summary_with_transactions(
            f"*Weekly Summary ({start_date} to {end_date})*", summary, start_date, end_date
        )

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

        # Catch-all must be last
        self.app.add_handler(MessageHandler(filters.COMMAND, self._unknown))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._unknown_text))

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.chat_id = update.effective_chat.id
        self._save_chat_id(self.chat_id)
        await update.message.reply_text(
            "Expense Tracker bot ready! Use the menu button or /help to see all commands."
        )

    async def _today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        text = self.format_daily_summary(today)
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
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        text = self.format_daily_summary(yesterday)
        await self._send_long_message(update, text)

    async def _week(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        today = datetime.now()
        start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        text = self.format_weekly_summary(start, end)
        await self._send_long_message(update, text)

    async def _month(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        today = datetime.now()
        start = f"{today.year}-{today.month:02d}-01"
        end = today.strftime("%Y-%m-%d")
        summary = self.storage.get_spending_summary(start_date=start, end_date=end)
        if summary["total"] == 0:
            await update.message.reply_text("No transactions this month")
            return
        text = self._build_summary_with_transactions(
            f"*Monthly Summary ({start} to {end})*", summary, start, end
        )
        await self._send_long_message(update, text)

    async def _add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

        now = datetime.now()
        tx_date = parsed["date"] or now.strftime("%Y-%m-%dT%H:%M:%S")
        category = parsed["category"]
        if not category and self.categorizer:
            category, _ = self.categorizer.categorize(parsed["merchant"])

        tx_id = self.storage.insert_transaction(
            source="manual",
            source_id=f"manual-{now.strftime('%Y%m%d%H%M%S')}-{parsed['amount']}",
            amount=parsed["amount"],
            merchant=parsed["merchant"],
            category=category,
            currency=currency,
            exchange_rate=exchange_rate,
            transaction_date=tx_date,
        )

        sgd_equivalent = parsed["amount"] * exchange_rate
        icon = self.storage.get_category_icon_map().get(category, "")
        cat_display = f"{icon} {self._escape_md(category)}" if icon else self._escape_md(category)
        msg = f"✅ *Added* #{tx_id}\n*{self._escape_md(parsed['merchant'])}* · {cat_display} · `${parsed['amount']:.2f} {currency}`"
        if currency != "SGD":
            msg += f"\n~ SGD `${sgd_equivalent:.2f}`"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _cash(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

        now = datetime.now()
        tx_date = parsed["date"] or now.strftime("%Y-%m-%dT%H:%M:%S")
        category = parsed["category"]
        if not category and self.categorizer:
            category, _ = self.categorizer.categorize(parsed["merchant"])

        tx_id = self.storage.insert_transaction(
            source="cash",
            source_id=f"cash-{now.strftime('%Y%m%d%H%M%S')}-{parsed['amount']}",
            amount=parsed["amount"],
            merchant=parsed["merchant"],
            category=category,
            transaction_date=tx_date,
        )
        icon = self.storage.get_category_icon_map().get(category, "")
        cat_display = f"{icon} {self._escape_md(category)}" if icon else self._escape_md(category)
        msg = f"✅ *Cash* #{tx_id}\n*{self._escape_md(parsed['merchant'])}* · {cat_display} · `${parsed['amount']:.2f} SGD`"
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def _recategorize(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Usage: /recategorize <transaction_id>")
            return
        try:
            tx_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Transaction ID must be a number")
            return

        tx = self.storage.get_transaction(tx_id)
        if not tx:
            await update.message.reply_text(f"Transaction #{tx_id} not found")
            return

        # If a category was provided, apply it directly
        if len(context.args) >= 2:
            new_category = context.args[1]
            valid_categories = [c["name"] for c in self.storage.get_categories()]
            if new_category not in valid_categories:
                await update.message.reply_text(
                    f"Invalid category '{new_category}'. Valid: {', '.join(valid_categories)}"
                )
                return

            old_category = tx["category"]
            self.storage.update_transaction(tx_id, category=new_category)

            merchant = tx["merchant"]
            if merchant:
                self.storage.set_merchant_override(merchant, new_category)
                if self.categorizer:
                    self.categorizer.reload_overrides(self.storage.get_merchant_overrides())

            await update.message.reply_text(
                f"Updated #{tx_id}: {old_category} -> {new_category}"
                + (f" (learned: {merchant} = {new_category})" if merchant else "")
            )
            return

        # No category provided — show a grid of category buttons
        categories = self.storage.get_categories()
        keyboard = get_category_keyboard(tx_id, [c["name"] for c in categories])
        merchant = tx["merchant"] or "Unknown"
        current_category = tx["category"] or "Other"
        await update.message.reply_text(
            f"Recategorize #{tx_id}: {merchant} (currently {current_category})",
            reply_markup=keyboard,
        )

    async def _income(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

        # Check if last token is a date
        if remaining:
            try:
                datetime.strptime(remaining[-1], "%Y-%m-%d")
                tx_date = remaining[-1]
                remaining = remaining[:-1]
            except ValueError:
                pass

        description = " ".join(remaining) if remaining else "Income"
        now = datetime.now()
        date_str = tx_date or now.strftime("%Y-%m-%dT%H:%M:%S")

        tx_id = self.storage.insert_transaction(
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
        today = datetime.now()
        start = f"{today.year}-{today.month:02d}-01"
        end = today.strftime("%Y-%m-%d")
        balance = self.storage.get_balance(start, end)

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
        today = datetime.now()
        start = f"{today.year}-{today.month:02d}-01"
        end = today.strftime("%Y-%m-%d")

        summary = self.storage.get_spending_summary(start, end)
        ranking = self.storage.get_merchant_ranking(start, end, limit=5)
        avg = self.storage.get_average_daily(start, end)

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
        rows = self.storage.conn.execute(
            "SELECT * FROM recurring_transactions ORDER BY avg_amount DESC"
        ).fetchall()
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
        overall = get_period_comparison(self.storage.conn, period="month")
        categories = get_category_comparison(self.storage.conn, period="month")

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
        merchants = get_top_merchants(self.storage.conn, limit=5)

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
        v = get_spending_velocity(self.storage.conn)

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
        report = generate_summary(self.storage.conn, report_type="monthly")

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

    def notify_text(self, text: str) -> None:
        """Send a plain text message. Called from background threads (e.g., APScheduler)."""
        if not self.chat_id:
            logger.debug("Cannot send text: no chat_id (send /start to the bot)")
            return
        if not self._loop or not self.app:
            logger.debug("Cannot send text: bot not started yet")
            return
        asyncio.run_coroutine_threadsafe(
            self.app.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="Markdown"),
            self._loop,
        )

    def notify_transaction(self, tx_id: int, amount: float, merchant: str, category: Optional[str], source: str) -> None:
        """Send a transaction notification. Called from the Gmail poller thread."""
        if not self.chat_id:
            logger.debug("Cannot notify: no chat_id (send /start to the bot)")
            return
        if not self._loop or not self.app:
            logger.debug("Cannot notify: bot not started yet")
            return
        asyncio.run_coroutine_threadsafe(
            self._async_notify(tx_id, amount, merchant, category, source),
            self._loop,
        )

    async def _async_notify(self, tx_id: int, amount: float, merchant: str, category: Optional[str], source: str) -> None:
        icon_map = self.storage.get_category_icon_map()
        if category and category != "Other":
            icon = icon_map.get(category, "")
            cat_display = f"{icon} {self._escape_md(category)}" if icon else self._escape_md(category)
            source_label = SOURCE_LABELS.get(source, source)
            text = f"💸 *${amount:.2f}* at *{self._escape_md(merchant)}*\n{cat_display} · {self._escape_md(source_label)}"
            await self.app.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="Markdown")
        else:
            categories = self.storage.get_categories()
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
            source_label = SOURCE_LABELS.get(source, source)
            text = f"💸 *${amount:.2f}* at *{self._escape_md(merchant)}*\n{self._escape_md(source_label)} · Pick a category:"
            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )

    async def _category_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        if not query.data.startswith("cat:"):
            return

        _, tx_id_str, category = query.data.split(":", 2)
        tx_id = int(tx_id_str)
        tx = self.storage.get_transaction(tx_id)
        if not tx:
            await query.edit_message_text("Transaction not found.")
            return

        self.storage.update_transaction(tx_id, category=category)
        merchant = tx["merchant"]
        if merchant:
            self.storage.set_merchant_override(merchant, category)
            if self.categorizer:
                self.categorizer.reload_overrides(self.storage.get_merchant_overrides())

        await query.edit_message_text(f"{merchant} → {category}")

    async def _recat_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        if not query.data.startswith("recat:"):
            return

        _, tx_id_str, category = query.data.split(":", 2)
        tx_id = int(tx_id_str)
        tx = self.storage.get_transaction(tx_id)
        if not tx:
            await query.edit_message_text("Transaction not found.")
            return

        old_category = tx["category"]
        self.storage.update_transaction(tx_id, category=category)
        merchant = tx["merchant"]
        if merchant:
            self.storage.set_merchant_override(merchant, category)
            if self.categorizer:
                self.categorizer.reload_overrides(self.storage.get_merchant_overrides())

        await query.edit_message_text(
            f"#{tx_id} {merchant}: {old_category} → {category}"
        )

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

    async def _send_daily_digest(self) -> None:
        """Send morning digest: yesterday's total, month-to-date, any alerts."""
        if not self.chat_id:
            logger.debug("Cannot send daily digest: no chat_id")
            return

        conn = self.storage.conn
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        today = datetime.now().strftime("%Y-%m-%d")

        # Yesterday's total
        yesterday_txs = self.storage.query_transactions(start_date=yesterday, end_date=yesterday)
        yesterday_total = sum(
            tx["amount"] * (tx.get("exchange_rate") or 1)
            for tx in yesterday_txs if tx["type"] == "expense"
        )

        # Month to date
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_txs = self.storage.query_transactions(start_date=month_start, end_date=today)
        month_total = sum(
            tx["amount"] * (tx.get("exchange_rate") or 1)
            for tx in month_txs if tx["type"] == "expense"
        )

        # Velocity, new merchants, anomalies
        velocity = get_spending_velocity(conn)
        new_merchants = check_new_merchants(conn)
        anomalies = get_anomalies(conn)

        lines = [
            "*Morning Digest*\n",
            f"Yesterday: *${yesterday_total:.2f}* ({len([t for t in yesterday_txs if t['type'] == 'expense'])} transactions)",
            f"Month to date: *${month_total:.2f}*\n",
        ]

        if velocity["status"] == "ahead":
            lines.append(f"⚠ Spending {velocity['pace_percent']:.0f}% of last month's pace")

        if new_merchants:
            lines.append(f"🛍 {len(new_merchants)} new merchant(s)")

        if anomalies:
            lines.append(f"⚠ {len(anomalies)} unusual transaction(s)")

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Insights", callback_data="cmd_insights"),
                InlineKeyboardButton("📋 Balance", callback_data="cmd_balance"),
            ],
        ])

        await self.app.bot.send_message(
            chat_id=self.chat_id,
            text="\n".join(lines),
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    def notify_daily_digest(self) -> None:
        """Schedule daily digest send. Called from APScheduler background thread."""
        if not self.chat_id:
            logger.debug("Cannot send daily digest: no chat_id")
            return
        if not self._loop or not self.app:
            logger.debug("Cannot send daily digest: bot not started")
            return
        asyncio.run_coroutine_threadsafe(self._send_daily_digest(), self._loop)

    def run(self) -> None:
        self.setup_handlers()
        logger.info("Starting Telegram bot")
        self.app.run_polling()
