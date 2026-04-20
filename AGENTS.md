# AGENTS.md — AI Agent Context

## Project Overview

Automatic Expense Tracker — a privacy-first Python service that ingests transaction data from Gmail (DBS PayLah!, UOB PayNow) and Apple Wallet push notifications, stores them in SQLite, and provides interaction via Telegram bot and a web dashboard.

## Architecture

Single Python monolith, one process, six subsystems:
1. **Gmail Poller** — scheduled polling of Gmail API for transaction emails, HTML body extraction fallback
2. **Webhook Receiver** — FastAPI endpoint receiving Apple Wallet data from iOS Shortcuts, cross-source dedup
3. **Parser Engine** — plugin-based bank/payment parsers (one class per source)
4. **Interaction Layer** — Telegram bot (commands + notifications + guided UX) + Web dashboard (dark fintech theme, Chart.js)
5. **Categorization** — keyword matching + learned merchant overrides, with match source tracking
6. **Intelligence** — recurring transaction detection, spending insights, multi-currency exchange rates

All data in SQLite with WAL mode. Single-user, single-password system. Supports income and expense tracking.

## Key Design Decisions

- `source_id` UNIQUE constraint prevents duplicate transactions
- Cross-source dedup: same merchant + amount from different sources within 10 minutes → single record
- `raw_data` column stores original payloads for re-parsing
- Categories auto-assigned via keyword matching, overridable via `/recategorize` (learns merchant overrides)
- `type` column distinguishes `expense` (default) from `income` transactions
- `exchange_rate` column normalizes foreign currency to SGD; all summaries use `amount * exchange_rate`
- Categorizer returns `(category, match_source)` tuple — match_source is `"learned"`, `"keyword:<kw>"`, or `"default"`
- Merchant overrides stored in `merchant_overrides` table, hot-reloadable via `categorizer.reload_overrides()`
- Recurring transactions detected by consistent amounts (±10%) and intervals (monthly 25-35 days, weekly 6-8 days)
- Exchange rates cached for 24 hours with fallback hardcoded rates when API unreachable
- All sensitive config in `config.yaml` (gitignored) or environment variables (Railway) — never committed

## File Responsibilities

| File | Purpose |
|------|---------|
| `src/main.py` | Entry point — starts all services, creates DB schema with migrations |
| `src/config.py` | Loads `config.yaml` + environment variable overrides, falls back to env-only config |
| `src/storage.py` | All SQLite operations — schema init, CRUD, queries, insights, income, merchant overrides |
| `src/categorizer.py` | Matches merchant names to categories via keywords + learned overrides, returns match source |
| `src/gmail_poller.py` | Scheduled Gmail API polling with HTML body extraction and per-bank dispatch |
| `src/webhook.py` | FastAPI POST endpoint for Apple Wallet payloads with cross-source dedup |
| `src/exchange.py` | Exchange rate service with API fetching, 24h caching, and fallback rates |
| `src/recurring.py` | Recurring transaction detection from spending patterns |
| `src/parsers/base.py` | Abstract `BankParser` — defines `can_parse()` / `parse()` |
| `src/parsers/dbs_paylah.py` | DBS PayLah! email → Transaction (SGD prefix, To: merchant, Transaction Ref) |
| `src/parsers/uob_paynow.py` | UOB PayNow email → Transaction |
| `src/parsers/apple_wallet.py` | Apple Wallet shortcut payload → Transaction |
| `src/telegram_bot.py` | Telegram bot: all commands, guided UX, merchant override learning |
| `src/web/app.py` | FastAPI app serving dashboard + API endpoints (summary, trend, merchants, insights, balance, recurring, categories CRUD) |
| `src/web/auth.py` | bcrypt password verify + session cookie management |
| `scripts/gmail_auth.py` | One-time Gmail OAuth browser flow |
| `Dockerfile` | Railway deployment image |

## Database Schema

```sql
-- Core tables
transactions (id, source, source_id UNIQUE, amount, currency, exchange_rate, type, merchant, description, category, transaction_date, ingested_at, raw_data)
categories (name PK, keywords, icon)
ingestion_state (source PK, last_processed_id, last_processed_at, updated_at)

-- v0.2 additions
merchant_overrides (merchant PK, category, source, updated_at)
recurring_transactions (id, merchant, avg_amount, frequency, category, first_seen, last_seen, occurrences)
```

## Testing

Run: `pytest tests/ -v`

All tests use in-memory SQLite (`:memory:`) — no files on disk.
127 tests across all modules.
Fixtures in `tests/conftest.py` provide pre-initialized DB connections and sample configs.

## Security

- `config.yaml` is gitignored — contains bot tokens, password hashes, Gmail credentials
- `credentials.json`, `token.json`, `.env` are all gitignored
- Never commit any file containing real tokens, passwords, or API keys
- Use `config.example.yaml` as the template — it has placeholder values only
- On Railway, credentials are base64-encoded env vars, decoded at startup

## Branching

- `feature/*` branches merge into `develop` for integration testing
- `develop` merges into `main` only for releases (with version tag + CHANGELOG)
- See README.md for detailed workflow
- NEVER commit directly to `develop` or `master`, always spawn feature or hotfix/bugfix branch before committing
- **Merge commits required:** When merging a feature branch into `develop`, always use `git merge --no-ff <branch>` to create an explicit merge commit. This preserves a clear history of when each feature was integrated. Never use fast-forward merges.

## Commit Style

- No co-author lines in commits
- Use conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Keep messages concise — describe what and why, not how

## Common Modifications

- **Adding a new bank parser:** Create `src/parsers/<bank>.py` extending `BankParser`, add sender filter to `config.yaml`, add test in `tests/test_parsers.py`
- **Adding a Telegram command:** Add handler in `src/telegram_bot.py`, register in `setup_handlers()`, follow existing command pattern
- **Changing the schema:** Update `src/main.py` `init_db()` + add `ALTER TABLE` migration, update `tests/conftest.py` schema
- **Adding an API endpoint:** Add route in `src/web/app.py` inside `create_dashboard_app()`, add `Depends(require_auth)`
- **Adding a category color:** Add CSS class `.cat-<name>` in `style.css` and update `CAT_COLORS` in `dashboard.js`
