# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-20

### Added

- **DBS PayLah! email parsing fix** — Updated regex to match real email format (`Amount: SGD8.20`, `To: MERCHANT`, `Transaction Ref`), with HTML body extraction fallback when emails lack `text/plain` MIME parts
- **Cross-source deduplication** — Same transaction reported by both Gmail and Apple Wallet is now counted once (matched by merchant + amount within 10-minute window)
- **Category management** — Full CRUD for categories via web settings page at `/settings` with keyword editor, merchant override cleanup, and category delete with transaction reassignment
- **Merchant override learning** — When a transaction is recategorized via `/recategorize`, the merchant → category mapping is learned and applied to future transactions from the same merchant. Overrides take priority over keyword matching
- **Categorizer match source tracking** — `categorize()` now returns `(category, match_source)` tuple where match_source is `"learned"`, `"keyword:<kw>"`, or `"default"`
- **Cash tracking** — `/cash <amount> <merchant> [category]` command for quick offline transaction entry
- **Multi-currency support** — Tag foreign currency expenses (e.g. `/add 500 THB street food`), auto-converted to SGD using cached exchange rates with fallback rates for offline use
- **Income tracking** — `type` column on transactions (`expense` / `income`), `/income` command to record income, `/balance` command showing earned/spent/net
- **Spending insights** — `/insights` Telegram command showing top merchants and average daily spend; `/api/insights`, `/api/trend`, `/api/merchants` API endpoints for dashboard
- **Recurring transaction detection** — Automatically detects subscriptions and regular payments (monthly/weekly) based on consistent amounts and intervals; `/subscriptions` Telegram command; `/api/recurring` API endpoint
- **Telegram guided UX** — Catch-all handler for unknown commands and plain text, contextual error messages with usage hints and examples, enhanced `/help` with structured command reference, redirects removed commands to web dashboard
- **Dashboard redesign** — Complete frontend rewrite with dark fintech theme (Sora + DM Sans fonts, custom color system), period selector (Day/Week/Month), donut and trend charts, insights panel, filterable/sortable transaction list with infinite scroll, PWA meta tags for iOS home screen
- **Railway deployment** — Dockerfile, environment variable configuration fallback (no `config.yaml` needed), Gmail credential decoding from base64 env vars, persistent volume support, updated setup guide
- **Income vs expense API** — `GET /api/balance` and `GET /api/income-vs-expense` endpoints for net position and monthly comparison

### Changed

- **Gmail poller dedup bug fix** — `is_duplicate()` now uses the parser's `source` (e.g. `"dbs_paylah"`) instead of hardcoded `"gmail"`, fixing a bug where previously-seen emails were re-processed every poll cycle
- **Gmail poller parse failure logging** — Logs full email body at WARNING level when DBS parser returns None, aiding regex tuning
- **Spending summary excludes income** — `get_spending_summary()` now filters to `type = 'expense'` only; income tracked separately via `get_income_summary()`
- **Commit style** — Merge commits required (`--no-ff`) for feature → develop merges

### Tests

- 127 tests passing (up from 66 in v0.1.0)
- New test files: `tests/test_gmail_poller.py`, `tests/test_exchange.py`, `tests/test_recurring.py`
- New test classes: `TestCrossSourceDedup`, `TestWebhookDedup`, `TestCategoryCRUD`, `TestMerchantOverrides`, `TestCategorizerOverrides`, `TestIncomeTracking`, `TestInsights`, `TestEnvConfig`

## [0.1.0] - 2026-04-17

### Added

- SQLite storage layer with CRUD operations and spending queries
- Configuration loader with YAML file + environment variable overrides
- Parser engine with DBS PayLah!, UOB PayNow, and Apple Wallet parsers
- Keyword-based auto-categorization engine
- Gmail polling pipeline with per-bank parser dispatch and OAuth flow
- Apple Wallet webhook receiver with 5-minute deduplication window
- Telegram bot with `/today`, `/week`, `/month`, `/add`, `/help` commands
- Web dashboard with Chart.js visualizations and bcrypt-gated auth
- Main entry point integrating all services with background threads
- Comprehensive `.gitignore` blocking all sensitive files (config, tokens, DBs)
- `README.md` with installation guide and iOS Shortcut setup instructions
- `AGENTS.md` for AI agent context
- `config.example.yaml` template with placeholder values
- 66 passing tests across all modules
