# Automatic Expense Tracker

A privacy-first expense tracking engine that automatically captures transactions from bank emails (DBS PayLah!, UOB PayNow, UOB Card) and Apple Wallet notifications. Zero manual input for day-to-day tracking — just spend and review via Telegram or the React web dashboard.

## Key Features

- **Gmail Auto-Ingestion** — Polls DBS PayLah!, UOB PayNow, and UOB Card transaction emails automatically, with HTML body fallback
- **Apple Wallet Capture** — iOS Shortcut pushes Apple Wallet notifications to your server; card name tracked alongside amount
- **Source-ID Deduplication** — Every transaction carries a unique `source_id`; cross-source duplicates (Gmail + Apple Wallet) are discarded automatically
- **Telegram Bot** — Real-time transaction alerts with inline categorisation, spending queries, manual entry, analytics commands, and a daily morning digest
- **React Web Dashboard** — Full SPA with Overview, Transactions, Analytics, and Settings pages; dark fintech theme, fully responsive
- **Analytics Engine** — Spending velocity, anomaly/unusual-spend detection, period-over-period comparison, merchant trends, and cached weekly/monthly reports
- **Auto-Categorisation** — Keyword matching with learned merchant overrides that persist across sessions
- **Category Management** — Full CRUD via the Settings page with keyword editor, icon and color picker, and merchant override cleanup
- **Multi-Currency** — Tag foreign currency expenses (e.g. `/add 500 THB street food`), auto-converted to SGD using cached exchange rates
- **Income Tracking** — Record income alongside expenses, see net balance via `/balance`
- **Recurring Detection** — Automatically detects subscriptions and regular payments (monthly/weekly)
- **Cash Tracking** — Quick `/cash` command for offline transactions
- **Scheduled Reports** — Daily morning digest, weekly and monthly summary delivered via Telegram
- **Railway Deployment** — Multi-stage Docker build (no Node.js in runtime image), one-click cloud hosting
- **Privacy-First** — All data stays in your own SQLite database. No third-party data sharing

## Architecture

```
Gmail API ──poll──> Parser Engine ──> SQLite <──> Telegram Bot
                       ^                ^    └──> Analytics Engine
                       │                │    └──> Web Dashboard (React SPA)
iOS Shortcut ──POST──> ┘                │              └── Overview
                                        │              └── Transactions
                                        │              └── Analytics
                                        └── Auto-categoriser   └── Settings
                                            └── Merchant Overrides
                                            └── Recurring Detector
                                            └── Exchange Rates
```

Single Python process. SQLite storage with WAL mode. FastAPI for webhooks and dashboard API. React SPA built with Vite, served from `dist/`.

## Prerequisites

- **Python 3.11+**
- **Node.js 22+** (only needed to rebuild the frontend — a pre-built `dist/` is included)
- **Gmail account** with API credentials (for email ingestion) — see setup guide
- **Telegram Bot Token** (from [@BotFather](https://t.me/botfather))
- **A [Railway](https://railway.app/) account** for cloud deployment

## Quick Start

### Local Development

```bash
# Clone and set up
git clone https://github.com/xinweichong/expense-tracker.git
cd expense-tracker
git checkout develop
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
# Edit config.yaml with your token, password hash, and webhook URL

# Gmail OAuth (one-time)
python scripts/gmail_auth.py

# Run
python src/main.py
```

The pre-built React frontend is committed in `src/web/dist/` and served automatically. To rebuild it after frontend changes:

```bash
cd src/web/frontend
npm ci
npm run build   # output goes to src/web/dist/
cd ../../..
```

### Generate Web Dashboard Password

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"
```

Copy the output (starts with `$2b$12$...`) into `config.yaml` as `web.password_hash`.

### Railway (Cloud) Deployment

No server needed — Railway hosts the app and provides a public HTTPS URL. The multi-stage Dockerfile builds the React frontend and produces a lean Python-only runtime image.

```bash
npm i -g @railway/cli && railway login
railway init
railway variables set TELEGRAM_BOT_TOKEN="your-token"
railway variables set WEB_PASSWORD_HASH="your-bcrypt-hash"
railway variables set GMAIL_CREDENTIALS_JSON="$(base64 -i credentials.json)"
railway variables set GMAIL_TOKEN_JSON="$(base64 -i token.json)"
railway variables set EXPENSE_DB_PATH="/data/expense_tracker.db"
# Add a persistent volume at /data via Railway dashboard (1GB)
railway up
```

See [docs/setup-guide.md](docs/setup-guide.md) for the full Railway walkthrough.

## Configuration

All configuration lives in `config.yaml` (gitignored). A template is provided at `config.example.yaml`.

```yaml
gmail:
  credentials_file: credentials.json
  poll_interval_seconds: 120
  sender_filters:
    - notification@dbs.com
    - notification@uob.com

server:
  host: "0.0.0.0"
  port: 8080
  webhook_base_url: "https://your-server.example.com"

web:
  password_hash: "<bcrypt hash>"

telegram:
  bot_token: "<from @BotFather>"

categories:
  - name: Food
    keywords: ["restaurant", "cafe", "food", "kopitiam", "toast box", "ya kun"]
    icon: "🍜"
  - name: Transport
    keywords: ["grab", "gojek", "comfortdelgro", "mrt", "bus", "taxi", "cdg"]
    icon: "🚗"
  - name: Shopping
    keywords: ["shopee", "lazada", "fairprice", "cold storage", "ntuc"]
    icon: "🛒"
  - name: Bills
    keywords: ["sp services", "singtel", "starhub", "m1"]
    icon: "📄"
  - name: Entertainment
    keywords: ["netflix", "spotify"]
    icon: "🎬"
  - name: Other
    keywords: []
    icon: "📌"
```

### Environment Variable Overrides

All config values can be set via environment variables (for Railway or Docker). When `config.yaml` is absent, the app builds its config entirely from env vars:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `WEB_PASSWORD_HASH` | bcrypt hash for dashboard |
| `PORT` | Server port (Railway sets this automatically) |
| `WEBHOOK_BASE_URL` | Public URL for Apple Wallet webhooks |
| `GMAIL_SENDER_FILTERS` | Comma-separated sender addresses |
| `GMAIL_CREDENTIALS_JSON` | Base64-encoded `credentials.json` |
| `GMAIL_TOKEN_JSON` | Base64-encoded `token.json` |
| `EXPENSE_DB_PATH` | Path to SQLite database |

## Telegram Commands

### Viewing Spending

| Command | Description |
|---------|-------------|
| `/today` | Today's spending summary |
| `/yesterday` | Yesterday's spending summary |
| `/week` | This week's summary |
| `/month` | This month's breakdown |
| `/balance` | Income vs expenses, net position |
| `/insights` | Top merchants, average daily spend |
| `/subscriptions` | Detected recurring transactions |

### Analytics

| Command | Description |
|---------|-------------|
| `/compare` | Period-over-period comparison (this period vs previous) |
| `/velocity` | Spending velocity, daily pace, and projected month-end total |
| `/merchants_report` | Top merchants ranked by total spend with trends |
| `/summary` | Cached weekly or monthly digest report |

### Manual Entry

| Command | Description | Example |
|---------|-------------|---------|
| `/add <amount> <merchant> [category] [date]` | Manual expense entry | `/add 12.50 Toast Box food` |
| `/cash <amount> <merchant> [category]` | Quick cash entry | `/cash 5.50 kopi` |
| `/income <amount> <description> [date]` | Record income | `/income 5000 salary` |
| `/add 500 THB street food` | Multi-currency (auto-converted to SGD) | — |

### Category Management

| Command | Description |
|---------|-------------|
| `/recategorize <id> <category>` | Change a transaction's category and learn the merchant mapping |

### Utilities

| Command | Description |
|---------|-------------|
| `/menu` | Quick-access button menu for common commands |
| `/dashboard` | Returns your dashboard URL |
| `/help` | Full command reference |
| Any unknown text | Bot responds with guidance and available commands |

All commands support **inline keyboards** — post-command action buttons appear automatically so you can drill deeper without typing follow-up commands. Transaction notifications include an inline category selection grid for instant recategorisation.

## Web Dashboard

Access at `http://your-server:8080`. The dashboard is a React SPA with four pages:

### Overview

- **Period selector** — Day / Week / Month tabs with forward/back date navigation
- **Hero total** — spending total for the period with income/expense split
- **Donut chart** — category breakdown with color-coded legend and tinted rows
- **Trend chart** — daily spending over time; switchable to per-category trend mode
- **Insights panel** — top merchants and average daily spend
- **Recent transactions** — latest entries with source/card badges and category icon pills

### Transactions

- **Filterable list** — filter by category, merchant, or date; sort by date, amount, or category
- **Infinite scroll** — loads more as you scroll, no pagination needed
- **Inline edit** — edit merchant, amount, category, currency, exchange rate, card/source, and date directly in the row
- **Add transaction form** — expense, income, cash, or multi-currency entry with merchant alias support
- **Transaction cards** — show SGD equivalent for foreign-currency transactions, source/card badge

### Analytics

- **Period comparison charts** — current vs previous period, category-level breakdown
- **Spending velocity ring** — daily pace indicator and projected month-end total
- **Merchant table** — top merchants ranked by spend with period-over-period trend
- **Unusual spend alerts** — highlighted in yellow with explanatory labels
- **New merchant alerts** — flags merchants not seen in the previous period

### Settings

- **Category CRUD** — create, edit, and delete categories with keyword editor, icon picker, and unique color picker
- **Merchant overrides** — view and delete learned merchant-to-category mappings
- **Live reload** — changes take effect immediately without restarting the server

The dashboard is **fully responsive** (iPhone, iPad, desktop) and **PWA-ready** — "Add to Home Screen" opens fullscreen on iOS.

## iOS Shortcut Setup (Apple Wallet Auto-Capture)

This sets up an iOS Automation that **automatically fires** whenever an Apple Wallet transaction occurs. The Shortcut extracts transaction details (date, card, merchant, amount) and POSTs them as JSON to your server webhook.

### Part A: Create the Automation

1. Open the **Shortcuts** app on your iPhone
2. Go to the **Automation** tab → tap **"+"** → **"Create Personal Automation"**
3. Scroll down or search for **"Transaction"** → select it
4. **Select the cards** you want to automate
5. Leave all **categories** checked
6. Don't filter on **Merchants**
7. Select **"Run Immediately"**
8. Leave **"Notify When Run"** off
9. Tap **"Next"** → **"New Blank Automation"**

### Part B: Date, Card, and Merchant (4-5 actions)

**Action 1 — Format the Date:**
- Search **"Format"** → choose **"Format Date"**
- Set Date to **"Current Date"**
- Set format to **Custom**: `dd/MM/yyyy HH:mm:ss`

**Action 2 — Escape quotes in Card:**
- **"Replace Text"**: replace `"` with `\"` in **Shortcut Input → Card or Pass**

**Action 3 — Set Card variable:**
- **"Set Variable"**: name `Card`, value = **Updated Text** from Action 2

**Action 4 — Escape quotes in Merchant:**
- **"Replace Text"**: replace `"` with `\"` in **Shortcut Input → Merchant**

**Action 5 — Set Merchant variable:**
- **"Set Variable"**: name `Merchant`, value = **Updated Text** from Action 4

### Part C: Send to Server (2 actions)

**Action 6 — Build JSON:**
- **"Text"** action with:
```json
{"card":"Card","date":"Formatted Date","merchant":"Merchant","amount":"Amount"}
```
- Replace `Card`, `Formatted Date`, and `Merchant` with the magic variables from Actions 3, 1, and 5
- Replace `Amount` with the **raw** magic variable **Shortcut Input → Amount** (not a Set Variable — tap the Amount placeholder and select the original Shortcut Input directly)

The server handles all currency parsing automatically — iOS sends the raw amount string (e.g. `"PLN 3.78"`, `"£12.50"`, `"S$9.90"`, or a bare `"12.50"` for SGD).

**Action 7 — POST to server:**
- **"Get Contents of URL"**
- URL: `https://YOUR-SERVER/webhook/apple-wallet`
- Method: **POST**
- Headers: `Content-Type: application/json`
- Request Body: **File** → the Text variable from Action 6

### Testing

1. Tap **play** to test manually
2. Add a temporary **"Show Result"** after the Text action to inspect the JSON
3. Make a real purchase and verify:
   - Check `logs/app.log` for `POST /webhook/apple-wallet - 200`
   - Send `/today` to the Telegram bot
4. Expect to refine over the first few purchases

## Testing

```bash
pip install -r requirements-dev.txt
python3 -m pytest tests/ -v
```

All tests use in-memory SQLite — no database files created on disk. 206 tests across all modules.

## Project Structure

```
expense-tracker/
├── src/
│   ├── main.py              # Entry point — starts all services, runs DB migrations
│   ├── config.py            # Config loader + env-var fallback
│   ├── storage.py           # SQLite CRUD, queries, insights, income, overrides
│   ├── categorizer.py       # Keyword matching + merchant overrides
│   ├── analytics.py         # Velocity, anomaly detection, comparison, merchant trends, reports
│   ├── gmail_poller.py      # Gmail API polling + HTML extraction
│   ├── telegram_bot.py      # All Telegram commands + inline keyboards + notifications
│   ├── webhook.py           # Apple Wallet webhook + source-ID dedup
│   ├── exchange.py          # Exchange rate fetching + 24h caching
│   ├── recurring.py         # Recurring transaction detection
│   ├── parsers/
│   │   ├── base.py          # BankParser abstract class
│   │   ├── dbs_paylah.py    # DBS PayLah! email parser
│   │   ├── uob_paynow.py    # UOB PayNow email parser
│   │   ├── uob_card.py      # UOB Card email parser (incl. transit transactions)
│   │   └── apple_wallet.py  # Apple Wallet webhook parser
│   └── web/
│       ├── app.py           # FastAPI routes — dashboard API + SPA serving
│       ├── auth.py          # bcrypt auth + session cookies
│       ├── dist/            # Pre-built React SPA (committed, served by FastAPI)
│       └── frontend/        # React source (Vite + Tailwind + shadcn/ui)
│           ├── src/
│           │   ├── pages/
│           │   │   ├── OverviewPage.tsx
│           │   │   ├── TransactionsPage.tsx
│           │   │   ├── AnalyticsPage.tsx
│           │   │   └── SettingsPage.tsx
│           │   ├── components/  # Shared UI components
│           │   ├── api/         # API client layer
│           │   └── hooks/       # Data-fetching hooks (React Query)
│           └── vite.config.ts
├── tests/                   # 206 tests, all in-memory SQLite
├── scripts/
│   └── gmail_auth.py        # One-time Gmail OAuth flow
├── Dockerfile               # Multi-stage build — Node builds frontend, Python runs it
├── requirements.txt         # Production Python deps
├── requirements-dev.txt     # Test/dev deps (pytest etc.)
├── config.example.yaml      # Config template with placeholder values
├── docs/
│   └── setup-guide.md       # Detailed setup + troubleshooting
└── CHANGELOG.md
```

## Troubleshooting

### Gmail

| Issue | Solution |
|-------|----------|
| Auth fails | Delete `token.json` and re-run `scripts/gmail_auth.py` |
| "This app isn't verified" | Click Advanced → Go to app. Add your Gmail as Test User in OAuth consent screen |
| No transactions appearing | Check `logs/app.log` for parser errors. Verify sender filters match actual email senders. Emails must be **unread** in Gmail |
| DBS emails not parsing | The parser uses the real `Amount: SGD8.20` / `To: MERCHANT` format. If emails look different, check `raw_data` in the database |

### Telegram

| Issue | Solution |
|-------|----------|
| Bot doesn't respond | Verify `bot_token`. Send `/start`. Check logs for errors |
| Unknown command | Bot shows available commands for any unrecognised input. Type `/help` for the full list, or `/menu` for buttons |
| `/add` gives "Invalid format" | Format: `/add 12.50 MerchantName [category] [YYYY-MM-DD]`. Amount must be a positive number |
| `/recategorize` says category not found | Use exact category names. Type `/recategorize` alone to see available categories |
| Inline buttons not appearing | Ensure `bot_token` is correct and `post_init` ran successfully — check logs for `Registered Telegram command menu` |

### Web Dashboard

| Issue | Solution |
|-------|----------|
| Login fails | Regenerate password hash: `python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"` |
| Charts empty | No transactions in the selected period. Try a wider date range or add transactions first |
| 401 on API calls | Session expired — you will be redirected to login automatically. Sessions last 30 days |
| Can't add/edit categories | Go to the **Settings** page (gear icon in the header) |
| Analytics page shows no data | Requires at least two periods of transactions for comparison. Add historical entries first |

### Apple Wallet / iOS Shortcuts

| Issue | Solution |
|-------|----------|
| Automation doesn't fire | Settings → Shortcuts → Advanced → enable "Allow Running Scripts". Check Focus modes |
| Server returns 400 | Add "Show Result" to inspect JSON payload. Verify amount is a number and merchant is not empty |
| Server unreachable | Verify the Railway URL works in Safari on your iPhone |
| Duplicate transactions | Server deduplicates by `source_id` (unique constraint); re-sent webhooks are silently ignored |

### Database

| Issue | Solution |
|-------|----------|
| SQLite locked errors | WAL mode is enabled by default. Ensure only one process accesses the DB file |
| Missing columns after update | Run `python src/main.py` once — migrations run automatically (`ALTER TABLE` adds missing columns) |

### Railway

| Issue | Solution |
|-------|----------|
| Deploy fails | Check `railway logs`. Ensure `Dockerfile` exists and `requirements.txt` is valid |
| Gmail not working | Verify `GMAIL_CREDENTIALS_JSON` and `GMAIL_TOKEN_JSON` are base64-encoded correctly: `base64 -i credentials.json` |
| Database resets on deploy | Add a persistent volume mounted at `/data` and set `EXPENSE_DB_PATH=/data/expense_tracker.db` |

## Git Workflow

```
feature/xxx ──merge --no-ff──> develop ──test──> main (tagged release)
```

- **feature branches** — all development work, always branched from `develop`
- **develop** — integration testing branch, merge commits required (`--no-ff`)
- **main** — production releases only, each tagged with a version number

## Documentation

- **[docs/setup-guide.md](docs/setup-guide.md)** — Full setup walkthrough with Telegram, Gmail, Railway, and troubleshooting
- **[CHANGELOG.md](CHANGELOG.md)** — Version history
- **[AGENTS.md](AGENTS.md)** — AI agent context and architecture notes

## License

Private project. All rights reserved.
