# AGENTS.md — AI Agent Context

## Project Overview

Automatic Expense Tracker — a local, privacy-first Python service that ingests transaction data from Gmail (DBS PayLah!, UOB PayNow) and Apple Wallet push notifications, stores them in SQLite, and provides interaction via Telegram bot and a web dashboard.

## Architecture

Single Python monolith, one process, four subsystems:
1. **Gmail Poller** — scheduled polling of Gmail API for transaction emails
2. **Webhook Receiver** — FastAPI endpoint receiving Apple Wallet data from iOS Shortcuts
3. **Parser Engine** — plugin-based bank/payment parsers (one class per source)
4. **Interaction Layer** — Telegram bot (commands + notifications) + Web dashboard (Chart.js)

All data in SQLite with WAL mode. No user accounts — single-user, single-password system.

## Key Design Decisions

- `source_id` UNIQUE constraint prevents duplicate transactions
- `raw_data` column stores original payloads for re-parsing
- Categories are auto-assigned via keyword matching, overridable via Telegram
- Amounts positive = expense (no income tracking)
- All sensitive config in `config.yaml` (gitignored) — never committed

## File Responsibilities

| File | Purpose |
|------|---------|
| `src/main.py` | Entry point — starts Gmail poller, webhook server, and Telegram bot |
| `src/config.py` | Loads `config.yaml` + environment variable overrides |
| `src/storage.py` | All SQLite operations — schema init, CRUD, queries |
| `src/categorizer.py` | Matches merchant names to categories via keywords |
| `src/gmail_poller.py` | Scheduled Gmail API polling with per-bank dispatch |
| `src/webhook.py` | FastAPI POST endpoint for Apple Wallet payloads |
| `src/parsers/base.py` | Abstract `BankParser` — defines `can_parse()` / `parse()` |
| `src/parsers/dbs_paylah.py` | DBS PayLah! email → Transaction |
| `src/parsers/uob_paynow.py` | UOB PayNow email → Transaction |
| `src/parsers/apple_wallet.py` | Apple Wallet shortcut payload → Transaction |
| `src/telegram_bot.py` | Telegram bot: commands, notifications, category overrides |
| `src/web/app.py` | FastAPI app serving dashboard + API endpoints |
| `src/web/auth.py` | bcrypt password verify + session cookie management |
| `scripts/gmail_auth.py` | One-time Gmail OAuth browser flow |

## Testing

Run: `pytest tests/ -v`

All tests use in-memory SQLite (`:memory:`) — no files on disk.
Fixtures in `tests/conftest.py` provide pre-initialized DB connections and sample configs.

## Security

- `config.yaml` is gitignored — contains bot tokens, password hashes, Gmail credentials
- `credentials.json`, `token.json`, `.env` are all gitignored
- Never commit any file containing real tokens, passwords, or API keys
- Use `config.example.yaml` as the template — it has placeholder values only

## Branching

- `feature/*` branches merge into `develop` for integration testing
- `develop` merges into `main` only for releases (with version tag + CHANGELOG)
- See README.md for detailed workflow

## Common Modifications

- **Adding a new bank parser:** Create `src/parsers/<bank>.py` extending `BankParser`, add sender filter to `config.yaml`, add test in `tests/test_parsers.py`
- **Adding a Telegram command:** Add handler in `src/telegram_bot.py`, follow existing command pattern
- **Changing the schema:** Update `src/storage.py` init function + add migration logic, update `tests/conftest.py` schema
