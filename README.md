# Automatic Expense Tracker

A privacy-first expense tracking engine that automatically captures transactions from bank emails (DBS PayLah!, UOB PayNow) and Apple Wallet notifications. Zero manual input for day-to-day tracking — just spend and review via Telegram or web dashboard.

## Key Features

- **Gmail Auto-Ingestion** — Polls DBS PayLah! and UOB PayNow transaction emails automatically, with HTML body fallback
- **Apple Wallet Capture** — iOS Shortcut pushes Apple Wallet notifications to your server
- **Cross-Source Deduplication** — Same transaction reported by Gmail and Apple Wallet? Counted once
- **Telegram Bot** — Real-time alerts, spending queries, manual entry, income tracking, insights, and subscription detection
- **Web Dashboard** — Dark fintech theme with period selector, donut and trend charts, insights panel, filterable transaction list
- **Auto-Categorization** — Keyword matching with learned merchant overrides that persist across sessions
- **Category Management** — Full CRUD via web settings page with keyword editor and merchant override cleanup
- **Multi-Currency** — Tag foreign currency expenses (e.g. `/add 500 THB street food`), auto-converted to SGD
- **Income Tracking** — Record income alongside expenses, see net balance via `/balance`
- **Spending Insights** — Top merchants, average daily spend, period comparisons
- **Recurring Detection** — Automatically detects subscriptions and regular payments
- **Cash Tracking** — Quick `/cash` command for offline transactions
- **Railway Deployment** — One-click cloud hosting, no computer needed
- **Privacy-First** — All data stays in SQLite. No third-party data sharing

## Architecture

```
Gmail API ──poll──> Parser Engine ──> SQLite <──> Telegram Bot
                       ^                ^    └──> Web Dashboard
                       │                │         └── Settings Page
iOS Shortcut ──POST──> ┘                └── Auto-categorizer
                                            └── Merchant Overrides
                                            └── Recurring Detector
                                            └── Exchange Rates
```

Single Python process. SQLite storage with WAL mode. FastAPI for webhooks and dashboard.

## Prerequisites

- **Python 3.11+**
- **Gmail account** with API credentials (for email ingestion) — see setup guide
- **Telegram Bot Token** (from [@BotFather](https://t.me/botfather))
- **One of:**
  - A server reachable from your iPhone (Tailscale, Cloudflare Tunnel, or public IP) for local deployment
  - A [Railway](https://railway.app/) account for cloud deployment (no server needed)

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

### Generate Web Dashboard Password

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"
```

Copy the output (starts with `$2b$12$...`) into `config.yaml` as `web.password_hash`.

### Railway (Cloud) Deployment

No server needed — Railway hosts the app and provides a public HTTPS URL.

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
| `/week` | This week's summary |
| `/month` | This month's breakdown |
| `/balance` | Income vs expenses, net position |
| `/insights` | Top merchants, average daily spend |
| `/subscriptions` | Detected recurring transactions |

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

### Other

| Command | Description |
|---------|-------------|
| `/help` | Full command reference |
| Any unknown text | Bot responds with guidance |

Category and subscription management is also available via the **web dashboard settings page** at `/settings`.

## Web Dashboard

Access at `http://your-server:8080`. Features:

- **Period selector** — Day / Week / Month tabs with date navigation
- **Hero total** — spending total with income/expense breakdown
- **Donut chart** — category breakdown with color legend
- **Trend chart** — daily spending over time with gradient fill
- **Insights panel** — top merchants and average daily spend
- **Filterable transaction list** — filter by category, merchant; sort by date, amount, or category
- **Settings page** (`/settings`) — category CRUD, keyword editing, learned merchant override management
- **Responsive** — works on iPhone, iPad, and desktop
- **PWA-ready** — "Add to Home Screen" opens fullscreen on iOS

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

### Part C: Amount (7 actions)

The amount from Apple Wallet is text, not a number. It needs parsing and negation.

**Action 6 — Strip non-numeric:**
- **"Replace Text"**: regex `[^\d\.]` → empty, in **Shortcut Input → Amount**
- Enable **"Regular Expression"**

**Action 7 — Set Amount variable:**
- **"Set Variable"**: name `Amount`, value = **Updated Text**

**Action 8 — Check for negative sign:**
- **"Match Text"**: search for `-` in **Amount** variable

**Action 9 — If NOT negative, negate:**
- **"If"**: **Matches** **"does not have any value"**

**Action 10 — Prepend negative (inside If):**
- **"Combine Text"**: `-` + **Amount** variable, separator empty

**Action 11 — Update Amount (inside If):**
- **"Set Variable"**: name `Amount`, value = **Combined Text**

### Part D: Send to Server (2 actions)

**Action 12 — Build JSON:**
- **"Text"** action with:
```json
{"card":"Card","date":"Formatted Date","merchant":"Merchant","amount":"Amount"}
```
(Replace placeholders with magic variables by tapping in the text field)

**Action 13 — POST to server:**
- **"Get Contents of URL"**
- URL: `https://YOUR-SERVER/webhook/apple-wallet`
- Method: **POST**
- Headers: `Content-Type: application/json`
- Request Body: **File** → the Text variable from Action 12

### Testing

1. Tap **play** to test manually
2. Add a temporary **"Show Result"** after the Text action to inspect the JSON
3. Make a real purchase and verify:
   - Check `logs/app.log` for `POST /webhook/apple-wallet - 200`
   - Send `/today` to the Telegram bot
4. Expect to refine over the first few purchases

## Testing

```bash
python3 -m pytest tests/ -v
```

All tests use in-memory SQLite — no database files created on disk.

## Project Structure

```
expense-tracker/
├── src/
│   ├── main.py              # Entry point
│   ├── config.py            # Config loader + env-var fallback
│   ├── storage.py           # SQLite CRUD, queries, insights
│   ├── categorizer.py       # Keyword matching + merchant overrides
│   ├── gmail_poller.py      # Gmail API polling + HTML extraction
│   ├── telegram_bot.py      # All Telegram commands + guided UX
│   ├── webhook.py           # Apple Wallet webhook + cross-source dedup
│   ├── exchange.py          # Exchange rate fetching + caching
│   ├── recurring.py         # Recurring transaction detection
│   ├── parsers/
│   │   ├── base.py          # BankParser abstract class
│   │   ├── dbs_paylah.py    # DBS PayLah! parser
│   │   ├── uob_paynow.py    # UOB PayNow parser
│   │   └── apple_wallet.py  # Apple Wallet parser
│   └── web/
│       ├── app.py           # FastAPI dashboard + API endpoints
│       ├── auth.py          # bcrypt auth + session cookies
│       └── static/
│           ├── index.html   # Dashboard (dark fintech theme)
│           ├── style.css    # Responsive dark theme
│           ├── dashboard.js # Chart.js + period selector + filters
│           ├── settings.html # Category management page
│           ├── settings.css  # Settings page styles
│           └── settings.js   # Category CRUD logic
├── tests/                   # 127 tests, all in-memory
├── scripts/
│   └── gmail_auth.py       # One-time Gmail OAuth flow
├── Dockerfile               # Railway deployment
├── config.example.yaml      # Config template
├── docs/
│   └── setup-guide.md      # Detailed setup + troubleshooting
└── requirements.txt
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
| Unknown command | Bot now shows available commands for any unrecognized input. Type `/help` for the full list |
| `/add` gives "Invalid format" | Format: `/add 12.50 MerchantName [category] [YYYY-MM-DD]`. Amount must be a positive number |
| `/recategorize` says category not found | Use exact category names. Type `/recategorize` alone to see available categories |

### Web Dashboard

| Issue | Solution |
|-------|----------|
| Login fails | Regenerate password hash: `python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"` |
| Charts empty | No transactions in the selected period. Try a wider date range or add transactions first |
| 401 on API calls | Session expired. Log in again. Sessions last 30 days |
| Can't add/edit categories | Go to `/settings` in the dashboard. Use the gear icon in the header |

### Apple Wallet / iOS Shortcuts

| Issue | Solution |
|-------|----------|
| Automation doesn't fire | Settings → Shortcuts → Advanced → enable "Allow Running Scripts". Check Focus modes |
| Server returns 400 | Add "Show Result" to inspect JSON payload. Verify amount is a number and merchant is not empty |
| Server unreachable | Verify URL works in Safari on iPhone. For Tailscale, both devices must be connected |
| Amount wrong sign | The If/End If block must contain the Combine Text + Set Variable actions |
| Duplicate transactions | Server deduplicates by `source_id` (unique constraint) + cross-source matching (merchant + amount within 10 minutes) |

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

- **feature branches** — all development work, always from `develop`
- **develop** — integration testing branch, merge commits required (`--no-ff`)
- **main** — production releases only, each tagged with a version number

## Documentation

- **[docs/setup-guide.md](docs/setup-guide.md)** — Full setup walkthrough with Telegram, Gmail, Tailscale, Railway, and troubleshooting
- **[CHANGELOG.md](CHANGELOG.md)** — Version history
- **[AGENTS.md](AGENTS.md)** — AI agent context and architecture notes

## License

Private project. All rights reserved.
