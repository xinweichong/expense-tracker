import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.categorizer import Categorizer
from src.storage import Storage

logger = logging.getLogger(__name__)


class TelegramBotService:
    def __init__(self, storage: Storage, bot_token: str, categorizer: Optional[Categorizer] = None):
        self.storage = storage
        self.bot_token = bot_token
        self.categorizer = categorizer
        self.app = None

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

    def format_daily_summary(self, date: str) -> str:
        summary = self.storage.get_spending_summary(start_date=date, end_date=date)
        if summary["total"] == 0:
            return f"No transactions on {date}"

        lines = [f"*Spending for {date}*", f"Total: ${summary['total']:.2f}", ""]
        for cat, total in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: ${total:.2f}")
        return "\n".join(lines)

    def format_weekly_summary(self, start_date: str, end_date: str) -> str:
        summary = self.storage.get_spending_summary(start_date=start_date, end_date=end_date)
        if summary["total"] == 0:
            return "No transactions in this period"

        lines = [f"*Weekly Summary ({start_date} to {end_date})*",
                 f"Total: ${summary['total']:.2f}", ""]
        for cat, total in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: ${total:.2f}")
        return "\n".join(lines)

    def setup_handlers(self) -> None:
        self.app = Application.builder().token(self.bot_token).build()

        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("today", self._today))
        self.app.add_handler(CommandHandler("week", self._week))
        self.app.add_handler(CommandHandler("month", self._month))
        self.app.add_handler(CommandHandler("add", self._add))
        self.app.add_handler(CommandHandler("cash", self._cash))
        self.app.add_handler(CommandHandler("recategorize", self._recategorize))
        self.app.add_handler(CommandHandler("help", self._help))

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Expense Tracker bot ready! Commands: /today /week /month /add /help"
        )

    async def _today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        summary = self.format_daily_summary(today)
        await update.message.reply_text(summary, parse_mode="Markdown")

    async def _week(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        today = datetime.now()
        start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        summary = self.format_weekly_summary(start, end)
        await update.message.reply_text(summary, parse_mode="Markdown")

    async def _month(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        today = datetime.now()
        start = f"{today.year}-{today.month:02d}-01"
        end = today.strftime("%Y-%m-%d")
        summary = self.storage.get_spending_summary(start_date=start, end_date=end)
        if summary["total"] == 0:
            await update.message.reply_text("No transactions this month")
            return
        lines = [f"*Monthly Summary ({start} to {end})*",
                 f"Total: ${summary['total']:.2f}", ""]
        for cat, total in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"  {cat}: ${total:.2f}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _add(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Usage: /add <amount> <merchant> [category] [date]")
            return
        text = " ".join(context.args)
        parsed = self.parse_add_command(text)
        if not parsed:
            await update.message.reply_text("Invalid format. Usage: /add <amount> <merchant> [category] [date]")
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
            transaction_date=tx_date,
        )
        await update.message.reply_text(
            f"Added: ${parsed['amount']:.2f} at {parsed['merchant']}"
            + (f" ({category})" if category else "")
            + f" [#{tx_id}]"
        )

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
        await update.message.reply_text(
            f"Cash: ${parsed['amount']:.2f} at {parsed['merchant']}"
            + (f" ({category})" if category else "")
            + f" [#{tx_id}]"
        )

    async def _recategorize(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args or len(context.args) < 2:
            await update.message.reply_text("Usage: /recategorize <transaction_id> <new_category>")
            return
        try:
            tx_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Transaction ID must be a number")
            return
        new_category = context.args[1]

        tx = self.storage.get_transaction(tx_id)
        if not tx:
            await update.message.reply_text(f"Transaction #{tx_id} not found")
            return

        valid_categories = [c["name"] for c in self.storage.get_categories()]
        if new_category not in valid_categories:
            await update.message.reply_text(
                f"Invalid category '{new_category}'. Valid: {', '.join(valid_categories)}"
            )
            return

        old_category = tx["category"]
        self.storage.update_transaction(tx_id, category=new_category)

        # Save as merchant override so future transactions auto-categorize
        merchant = tx["merchant"]
        if merchant:
            self.storage.set_merchant_override(merchant, new_category)
            if self.categorizer:
                self.categorizer.reload_overrides(self.storage.get_merchant_overrides())

        await update.message.reply_text(
            f"Updated #{tx_id}: {old_category} -> {new_category}"
            + (f" (learned: {merchant} = {new_category})" if merchant else "")
        )

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = """*Commands:*
/today — Today's spending
/week — This week's summary
/month — This month's summary
/add <amount> <merchant> [category] [date] — Manual entry
/recategorize <tx_id> <category> — Change category and learn override
/search <merchant> — Find transactions
/category <name> — Category spending this month"""
        await update.message.reply_text(help_text, parse_mode="Markdown")

    def run(self) -> None:
        self.setup_handlers()
        logger.info("Starting Telegram bot")
        self.app.run_polling()
