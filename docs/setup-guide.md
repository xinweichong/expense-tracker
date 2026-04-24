# Setup Guide — Getting Everything Running

This guide walks you through every step to get Cashe fully operational: Telegram bot, Gmail email ingestion, Railway cloud deployment, and configuring which emails are crawled.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Setup](#2-project-setup)
3. [Telegram Bot Setup](#3-telegram-bot-setup)
4. [Gmail API Setup](#4-gmail-api-setup)
5. [Configuration](#5-configuration)
6. [Running the Application](#6-running-the-application)
7. [iOS Shortcut Setup](#7-ios-shortcut-setup)
8. [Configuring Email Addresses](#8-configuring-email-addresses)
9. [Adding a New Bank](#9-adding-a-new-bank)
10. [Running as a Service](#10-running-as-a-service)
11. [Troubleshooting](#11-troubleshooting)
12. [Railway Deployment](#12-railway-deployment)

---

## 1. Prerequisites

- **Python 3.11+** (for local development)
- **A Gmail account** that receives bank transaction emails
- **An iPhone** for Telegram + Apple Wallet
- **A [Railway](https://railway.app/) account** for cloud deployment

---

## 2. Project Setup

```bash
# Clone the repo
git clone https://github.com/xinweichong/expense-tracker.git
cd expense-tracker
git checkout develop

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy the config template
cp config.example.yaml config.yaml
```

At this point `config.yaml` exists but has placeholder values. You'll fill them in as you complete each step below.

---

## 3. Telegram Bot Setup

The Telegram bot is your primary interface — you'll use it to view spending, add manual transactions, and get real-time alerts.

### 3.1 Create the Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. BotFather will ask for:
   - **Bot display name** — e.g. `My Expense Tracker`
   - **Bot username** — must end in `bot`, e.g. `xinwei_expense_bot`
4. BotFather responds with your **bot token** — it looks like:
   ```
   7123456789:AAHfG3k9dBz8VqX2nLm5pRtYwKj7cF6sDxE
   ```
5. **Save this token.** You'll put it in `config.yaml`.

### 3.2 Start a Chat with the Bot

1. Search for your bot's username in Telegram
2. Tap **Start** (or send `/start`)
3. The bot won't respond yet — that's fine. It will respond once the server is running.

### 3.3 Add the Token to Config

Edit `config.yaml`:

```yaml
telegram:
  bot_token: "7123456789:AAHfG3k9dBz8VqX2nLm5pRtYwKj7cF6sDxE"
```

### 3.4 Alternative: Environment Variable

If you prefer not to store the token in the config file:

```bash
export TELEGRAM_BOT_TOKEN="7123456789:AAHfG3k9dBz8VqX2nLm5pRtYwKj7cF6sDxE"
```

The application checks `TELEGRAM_BOT_TOKEN` env var first and uses it to override the config file value.

---

## 4. Gmail API Setup

This enables the app to read your bank transaction emails (DBS PayLah!, UOB PayNow, etc.). It uses **read-only** access — the app never sends or modifies emails.

### 4.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** → **"New Project"**
3. Name it e.g. `Expense Tracker` → **Create**
4. Make sure the new project is selected (top-left dropdown)

### 4.2 Enable the Gmail API

1. Go to **APIs & Services → Library**
2. Search for **"Gmail API"**
3. Click it → **Enable**

### 4.3 Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **"+ Create Credentials"** → **"OAuth client ID"**
3. If prompted, configure the OAuth consent screen first:
   - User Type: **External**
   - App name: `Expense Tracker`
   - User support email: your email
   - Developer contact: your email
   - Skip scopes for now
   - Add your Gmail address as a **Test User** (important — the app stays in "Testing" mode)
4. Back to Credentials → **OAuth client ID**:
   - Application type: **Desktop app**
   - Name: `Expense Tracker`
5. Click **Create** — you'll see your Client ID and Client Secret
6. **Download the JSON file** (click the download icon) → rename it to `credentials.json`
7. Place `credentials.json` in the **root of the project directory** (same folder as `config.yaml`)

> `credentials.json` is gitignored — it will never be committed.

### 4.4 Run the One-Time Auth Flow

```bash
source venv/bin/activate
python scripts/gmail_auth.py
```

This will:
1. Open your browser to a Google sign-in page
2. Ask you to sign in with the Gmail account that receives bank emails
3. Show a "This app isn't verified" warning — click **Advanced** → **Go to Expense Tracker (unsafe)**
4. Ask you to grant read-only Gmail access — **Allow**
5. Complete and save `token.json` in the project root

> `token.json` is also gitignored. The refresh token inside it lets the app read emails indefinitely without re-authenticating.

### 4.5 Verify

After completing the auth flow, you should see both files in the project root:

```
credentials.json   ← from step 4.3
token.json          ← from step 4.4
```

Both are gitignored — run `git status` to confirm they don't show up.

---

## 5. Configuration

Edit `config.yaml` with your actual values:

```yaml
# Gmail polling settings
gmail:
  credentials_file: credentials.json     # path to the OAuth credentials JSON
  poll_interval_seconds: 120             # how often to check for new emails (seconds)
  sender_filters:                        # which senders to look for
    - notification@dbs.com               # DBS PayLah!
    - notification@uob.com               # UOB PayNow

# Server settings
server:
  host: "0.0.0.0"                        # listen on all interfaces
  port: 8080                             # port for web dashboard + webhooks
  webhook_base_url: "https://your-app.up.railway.app"  # your Railway URL

# Web dashboard password
web:
  password_hash: "$2b$12$..."            # generate this below

# Telegram bot
telegram:
  bot_token: "7123456789:AAHf..."        # from @BotFather (step 3.1)

# Auto-categorization rules
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

### 5.1 Generate the Web Dashboard Password

```bash
source venv/bin/activate
python -c "import bcrypt; print(bcrypt.hashpw(b'your-actual-password', bcrypt.gensalt()).decode())"
```

Copy the output (starts with `$2b$12$...`) and paste it as `web.password_hash`.

### 5.2 Set the Webhook URL

This is the URL your iPhone will POST Apple Wallet transactions to:

- **Railway:** `https://your-app.up.railway.app` (from the Railway dashboard)

The full webhook path is: `{webhook_base_url}/webhook/apple-wallet`

---

## 6. Running the Application

```bash
source venv/bin/activate
python src/main.py
```

You should see output like:
```
2026-04-17 10:00:00 [src.gmail_poller] INFO: Gmail authenticated successfully
2026-04-17 10:00:00 [src.gmail_poller] INFO: Gmail poller started (interval: 120s)
2026-04-17 10:00:00 [src.telegram_bot] INFO: Telegram bot started
2026-04-17 10:00:00 [__main__] INFO: Starting web server on 0.0.0.0:8080
```

### Verify each component:

**Telegram bot:**
- Open Telegram → send `/start` to your bot
- It should reply: `Expense Tracker bot ready! Commands: /today /week /month /add /help`
- Try `/today` — should say "No transactions on 2026-04-17" (or show any existing data)

**Web dashboard:**
- Open `https://your-app.up.railway.app` in a browser
- Enter the password you set in `web.password_hash`
- You should see the dashboard with empty charts

**Gmail poller:**
- If Gmail credentials are present, the poller starts automatically
- It processes the last 30 days of emails on first run, then polls every 2 minutes
- Send `/today` to the Telegram bot to check if transactions appeared

---

## 7. iOS Shortcut Setup (Apple Wallet)

See the detailed iOS Shortcut instructions in the [README.md](../README.md) under "iOS Shortcut Setup". The key points:

1. Open Shortcuts → Automation → Transaction trigger
2. Build ~14 actions to extract date, card, merchant, amount
3. POST JSON to `https://your-app.up.railway.app/webhook/apple-wallet`
4. Set to **Run Immediately** with no notification

---

## 8. Configuring Email Addresses

The Gmail poller checks for unread emails from specific senders. This is controlled by two things:

### 8.1 Sender Filters in config.yaml

The `sender_filters` list tells the poller which email addresses to look for:

```yaml
gmail:
  sender_filters:
    - notification@dbs.com        # DBS PayLah! transaction alerts
    - notification@uob.com        # UOB PayNow transaction alerts
```

The poller constructs a Gmail query like:
```
(from:notification@dbs.com OR from:notification@uob.com) is:unread
```

### 8.2 How to Find the Exact Sender Address

If you're unsure what email address your bank sends from:

1. Open Gmail in a browser
2. Find a transaction email from your bank
3. Click the **sender name** to reveal the actual email address
4. It might be something like `no-reply@dbs.com` or `alerts@uob.com.sg` — use the exact address

Common Singapore bank notification senders:

| Bank | Service | Likely sender |
|------|---------|---------------|
| DBS | PayLah! | `notification@dbs.com` |
| UOB | PayNow | `notification@uob.com` |
| OCBC | Pay Anyone | `no-reply@ocbc.com` |
| Citi | Citi Pay | `alerts@citi.com` |

> These are starting points — **always verify by checking actual emails in your Gmail**. Banks sometimes change their sender addresses.

### 8.3 Adding or Removing Senders

Edit `config.yaml` and update the list:

```yaml
gmail:
  sender_filters:
    - notification@dbs.com
    - notification@uob.com
    - no-reply@ocbc.com       # ← adding OCBC
```

Then restart the application. The poller will start checking for emails from the new sender on the next poll cycle.

### 8.4 Poll Interval

The `poll_interval_seconds` controls how often Gmail is checked:

```yaml
gmail:
  poll_interval_seconds: 120    # check every 2 minutes (default)
```

- Minimum recommended: `60` (1 minute) — don't go lower to avoid Gmail API rate limits
- Maximum practical: `300` (5 minutes) — for low-volume users
- Default: `120` (2 minutes)

---

## 9. Adding a New Bank

To support a bank that isn't DBS PayLah! or UOB PayNow, you need a new parser.

### 9.1 Create the Parser

Create `src/parsers/<bank_name>.py`:

```python
import re
from typing import Optional
from src.parsers.base import BankParser, ParseResult


class MyBankParser(BankParser):
    sender_domain = "mybank.com"  # must match the sender filter in config

    # Write a regex that matches the transaction email format
    TRANSACTION_PATTERN = re.compile(
        r"You spent \$([0-9,]+\.\d{2}) at (.+?) on",
        re.IGNORECASE,
    )

    def can_parse(self, sender: str, subject: str) -> bool:
        return self.sender_domain in sender.lower()

    def parse(self, email_body: str) -> Optional[ParseResult]:
        match = self.TRANSACTION_PATTERN.search(email_body)
        if not match:
            return None
        amount_str = match.group(1).replace(",", "")
        merchant = match.group(2).strip()
        return ParseResult(
            source="mybank",
            source_id=None,       # set by the Gmail poller
            amount=float(amount_str),
            merchant=merchant,
            description=email_body.strip(),
            raw_data=email_body,
        )
```

### 9.2 Register the Parser

Edit `src/parsers/__init__.py` to import and register it:

```python
from src.parsers.mybank import MyBankParser
ALL_PARSERS = [DbsPaylahParser, UobParser, MyBankParser]
```

### 9.3 Add to main.py

Edit `src/main.py` to instantiate the parser:

```python
from src.parsers.mybank import MyBankParser
# ...
parsers = [DbsPaylahParser(), UobParser(), MyBankParser()]
```

### 9.4 Add Sender Filter

Edit `config.yaml`:

```yaml
gmail:
  sender_filters:
    - notification@dbs.com
    - notification@uob.com
    - notification@mybank.com    # ← new
```

### 9.5 Test

1. Find a real email from the bank in your Gmail
2. Copy the email body text
3. Write a test in `tests/test_parsers.py`:

```python
class TestMyBankParser:
    def setup_method(self):
        self.parser = MyBankParser()

    def test_parse_transaction(self):
        body = """<paste real email body here>"""
        result = self.parser.parse(body)
        assert result is not None
        assert result.amount == 12.50
        assert result.merchant == "Expected Merchant Name"
```

4. Iterate on the regex until it extracts the correct amount and merchant.

---

## 10. Running as a Service

### macOS — launchd

Create `~/Library/LaunchAgents/com.expense-tracker.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.expense-tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/xinweichong/personal/expense-tracker/venv/bin/python</string>
        <string>/Users/xinweichong/personal/expense-tracker/src/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/xinweichong/personal/expense-tracker</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/xinweichong/personal/expense-tracker/logs/launchd-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/xinweichong/personal/expense-tracker/logs/launchd-stderr.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.expense-tracker.plist
```

Check status:
```bash
launchctl list | grep expense-tracker
```

Stop:
```bash
launchctl unload ~/Library/LaunchAgents/com.expense-tracker.plist
```

### Linux — systemd

Create `/etc/systemd/system/expense-tracker.service`:

```ini
[Unit]
Description=Expense Tracker
After=network.target

[Service]
Type=simple
User=xinweichong
WorkingDirectory=/home/xinweichong/expense-tracker
ExecStart=/home/xinweichong/expense-tracker/venv/bin/python src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable expense-tracker
sudo systemctl start expense-tracker
sudo systemctl status expense-tracker
```

View logs:
```bash
sudo journalctl -u expense-tracker -f
```

---

## 11. Troubleshooting

### Gmail

| Problem | Fix |
|---------|-----|
| `gmail_auth.py` fails with "file not found" | Make sure `credentials.json` is in the project root directory |
| "This app isn't verified" warning | Click Advanced → Go to app. Your Gmail address must be added as a Test User in the OAuth consent screen |
| Token expired / auth errors | Delete `token.json` and re-run `python scripts/gmail_auth.py` |
| No emails being processed | Check `logs/app.log` for errors. Verify the sender addresses in `sender_filters` match the actual email senders. Make sure the emails are **unread** in Gmail. |
| Emails processed but wrong amount/merchant | The parser regex might not match the email format. Check `raw_data` in the database for the actual email content and adjust the regex. |

### Telegram

| Problem | Fix |
|---------|-----|
| Bot doesn't respond | Verify `bot_token` in `config.yaml` is correct. Check the bot is running (see logs). Try `/start` first. |
| Bot not sending alerts | Alerts are only sent for new transactions after the bot starts. Old transactions won't trigger alerts. |
| `/add` gives "Invalid format" | Format is: `/add 12.50 MerchantName [category] [YYYY-MM-DD]`. Amount must be a number. |

### Web Dashboard

| Problem | Fix |
|---------|-----|
| Login fails | Regenerate the password hash: `python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"` |
| Charts empty | No transactions in the selected date range. Use the date picker to adjust. |
| 401 on API calls | Session cookie expired. Log in again. Sessions last 30 days. |

### Apple Wallet

| Problem | Fix |
|---------|-----|
| Shortcut doesn't fire on transactions | Go to Settings → Shortcuts → Advanced → enable "Allow Running Scripts". Check Focus modes. |
| Server returns 400 | The JSON payload is malformed. Add a "Show Result" action in the Shortcut to inspect the JSON before sending. |
| Amount shows as positive instead of negative | Check the If block in the Shortcut — the Combine Text + Set Variable must be inside the If condition. |
| Takes ~8 purchases to get working | Normal. Each real transaction lets you verify the Shortcut output and tweak the regex or payload format. |

### Railway

| Problem | Fix |
|---------|-----|
| Deploy fails | Check `railway logs`. Ensure `Dockerfile` exists and `requirements.txt` is valid |
| Gmail not working | Verify `GMAIL_CREDENTIALS_JSON` and `GMAIL_TOKEN_JSON` are base64-encoded correctly: `base64 -i credentials.json` |
| Database resets on deploy | Add a persistent volume mounted at `/data` and set `EXPENSE_DB_PATH=/data/expense_tracker.db` |
| Server unreachable from iPhone | Verify the Railway URL works in Safari on your iPhone |

### Logs

All logs go to:
- **Console output** — visible in the terminal
- **File** — `logs/app.log` (rotated at 10MB, keeps 5 files)

Check logs for errors:
```bash
tail -f logs/app.log
```

Search for specific errors:
```bash
grep -i error logs/app.log
grep "POST /webhook" logs/app.log
grep "Gmail authenticated" logs/app.log
```

---

## 12. Railway Deployment

Deploy the expense tracker to [Railway](https://railway.app/) for a cloud-hosted setup that doesn't require your local machine to stay on.

### 12.1 Create a Railway Account

1. Go to [railway.app](https://railway.app/) and sign up (GitHub login is easiest)
2. Verify your email if prompted

### 12.2 Install the Railway CLI

```bash
npm i -g @railway/cli
railway login
```

This opens a browser to authenticate your CLI session.

### 12.3 Initialize the Project

```bash
cd expense-tracker
railway init
```

Select **"Empty project"** and give it a name like `expense-tracker`. Railway creates a new project and links this directory.

### 12.4 Set Environment Variables

In the Railway dashboard (or via CLI), set these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from @BotFather | `7123456789:AAHfG3k9dBz8VqX2nLm5pRtYwKj7cF6sDxE` |
| `WEB_PASSWORD_HASH` | bcrypt hash of your dashboard password | `$2b$12$...` |
| `GMAIL_SENDER_FILTERS` | Comma-separated sender addresses | `notification@dbs.com,notification@uob.com` |
| `GMAIL_CREDENTIALS_JSON` | Base64-encoded `credentials.json` | (see below) |
| `GMAIL_TOKEN_JSON` | Base64-encoded `token.json` | (see below) |
| `EXPENSE_DB_PATH` | Database path on persistent volume | `/data/expense_tracker.db` |
| `WEBHOOK_BASE_URL` | Your Railway public URL | `https://expense-tracker.up.railway.app` |

To encode your Gmail credential files as base64:

```bash
# macOS / Linux
base64 -i credentials.json
base64 -i token.json

# Copy the output and set it as the env var value
```

Alternatively via CLI:

```bash
railway variables set TELEGRAM_BOT_TOKEN="your-token"
railway variables set WEB_PASSWORD_HASH="your-hash"
railway variables set GMAIL_SENDER_FILTERS="notification@dbs.com,notification@uob.com"
railway variables set GMAIL_CREDENTIALS_JSON="$(base64 -i credentials.json)"
railway variables set GMAIL_TOKEN_JSON="$(base64 -i token.json)"
railway variables set EXPENSE_DB_PATH="/data/expense_tracker.db"
```

### 12.5 Add a Persistent Volume

The database must survive redeployments. Add a volume mounted at `/data`:

1. Go to your project in the Railway dashboard
2. Click **"New"** -> **"Volume"**
3. Set mount path: `/data`
4. Set size: **1 GB** (sufficient for years of transaction data)

### 12.6 Deploy

```bash
railway up
```

Railway detects the Dockerfile, builds the image, and deploys. The first deploy takes a few minutes.

Check logs:

```bash
railway logs
```

You should see:
```
Gmail credentials decoded from environment
Gmail poller started (interval: 120s)
Telegram bot started
Starting web server on 0.0.0.0:8080
```

### 12.7 Get the Public URL

Railway assigns a public URL automatically. Find it in the Railway dashboard under **Settings** -> **Networking** -> **Public URL**, or via CLI:

```bash
railway domain
```

Update the `WEBHOOK_BASE_URL` env var to match:

```bash
railway variables set WEBHOOK_BASE_URL="https://your-app.up.railway.app"
```

Then redeploy:

```bash
railway up
```

### 12.8 Update iOS Shortcut

Change the webhook URL in your iOS Shortcut to point to the Railway URL:

- Old: `http://100.64.0.1:8080/webhook/apple-wallet`
- New: `https://your-app.up.railway.app/webhook/apple-wallet`

### 12.9 How It Works

When deployed on Railway:

1. **No `config.yaml` needed** -- all configuration comes from environment variables
2. **Gmail credentials** are decoded from base64 env vars (`GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON`) and written to disk at startup
3. **Database** persists on the mounted volume at `/data/expense_tracker.db`
4. **PORT** is automatically set by Railway and respected by the application
5. **Logs** go to stdout (captured by Railway's log system) and to `logs/app.log` on the container filesystem
