# Setup Guide — Getting Everything Running

This guide walks you through every step to get Cashe fully operational: Telegram bot, Gmail email ingestion, Oracle Cloud deployment, and configuring which emails are crawled.

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
12. [Oracle Cloud Deployment](#12-oracle-cloud-deployment)

---

## 1. Prerequisites

- **Python 3.11+** (for local development)
- **A Gmail account** that receives bank transaction emails
- **An iPhone** for Telegram + Apple Wallet
- **An [Oracle Cloud](https://cloud.oracle.com/) Always Free account** for cloud deployment
- **A [Cloudflare](https://cloudflare.com/) account with a domain** for the Tunnel + TLS

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
  webhook_base_url: "https://cashe.yourdomain.com"       # your Cloudflare Tunnel public hostname

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

- **Oracle Cloud + Cloudflare Tunnel:** `https://cashe.yourdomain.com`

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
- Open `https://cashe.yourdomain.com` in a browser
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
3. POST JSON to `https://cashe.yourdomain.com/webhook/apple-wallet`
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

### Oracle Cloud / Docker

| Problem | Fix |
|---------|-----|
| Container won't start | Run `docker compose logs app` — check that `config.yaml` and `credentials.json` are present in the repo root on the VM |
| Gmail not authenticating | Verify `token.json` is in `data/` on the VM; re-run `python scripts/gmail_auth.py` locally and SCP the new `token.json` |
| Tunnel not connecting | Run `docker compose logs cloudflared`. Check `TUNNEL_TOKEN` in `.env`. The tunnel should show as healthy in Cloudflare Zero Trust |
| Database lost on redeploy | It shouldn't be — `data/` is bind-mounted. Use `docker compose down` (not `--volumes`) to stop without wiping it |
| Server unreachable from iPhone | Confirm `https://cashe.yourdomain.com` loads in Safari. Check the Cloudflare Tunnel status and that the public hostname is set to `http://app:8080` |

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

## 12. Oracle Cloud Deployment

Deploy Cashe to an **Oracle Always Free** ARM VM with a **Cloudflare Tunnel** for public HTTPS access — no open inbound ports, no TLS certificates to manage, and a custom domain on the free plan.

### 12.1 Provision an Oracle Cloud VM

1. Sign up at [cloud.oracle.com](https://cloud.oracle.com/) — the Always Free tier requires a credit card but charges nothing
2. Go to **Compute → Instances → Create Instance**
3. Choose:
   - **Image:** Ubuntu 22.04 (Minimal)
   - **Shape:** `VM.Standard.A1.Flex` — set **1 OCPU / 6 GB RAM** minimum (up to 4 OCPU / 24 GB are free)
4. Under **Networking**, ensure a public IPv4 address is assigned
5. Under **Add SSH keys**, upload your public key (`~/.ssh/id_rsa.pub`)
6. Create the instance and note the **Public IP**

Add an SSH alias to `~/.ssh/config` for convenience:

```
Host cashe-ssh
    HostName YOUR_VM_PUBLIC_IP
    User ubuntu
    IdentityFile ~/.ssh/id_rsa
```

Verify SSH works: `ssh cashe-ssh`

### 12.2 Install Docker on the VM

```bash
ssh cashe-ssh
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in, or run: newgrp docker
docker run hello-world   # verify
```

### 12.3 Create a Cloudflare Tunnel

1. In the Cloudflare dashboard go to **Zero Trust → Networks → Tunnels**
2. Click **Create a tunnel** → name it (e.g. `cashe`) → **Save tunnel**
3. Copy the **tunnel token** shown on screen
4. Under **Public Hostname**, add:
   - Subdomain: `cashe`
   - Domain: `yourdomain.com`
   - Service: `http://app:8080`
5. Save — Cloudflare provisions the DNS record automatically

### 12.4 Clone and Configure on the VM

```bash
ssh cashe-ssh
git clone https://github.com/xinweichong/expense-tracker.git
cd expense-tracker
git checkout develop
cp .env.example .env
nano .env   # paste in TUNNEL_TOKEN=<your token from step 12.3>
mkdir -p data
```

### 12.5 Copy Credentials from Your Local Machine

Run these on your **local machine**:

```bash
scp config.yaml cashe-ssh:~/expense-tracker/
scp credentials.json cashe-ssh:~/expense-tracker/
scp token.json cashe-ssh:~/expense-tracker/data/
```

Ensure `config.yaml` has the correct `webhook_base_url`:

```yaml
server:
  webhook_base_url: "https://cashe.yourdomain.com"
```

### 12.6 First Deploy

On the VM:

```bash
cd ~/expense-tracker
docker compose up -d --build
```

The first build takes a few minutes (downloads base images, builds React frontend, installs Python deps). Check progress:

```bash
docker compose logs -f
```

You should eventually see:

```
Database ready: X transactions, Y categories
Gmail authenticated successfully
Telegram bot started
Starting web server on 0.0.0.0:8080
```

### 12.7 Verify

1. Open `https://cashe.yourdomain.com` in a browser — you should reach the login page
2. Send `/start` to your Telegram bot — it should respond
3. Make a test payment and confirm the Apple Wallet webhook fires

### 12.8 Subsequent Deploys

After merging changes to `develop` on GitHub, deploy by running on the VM:

```bash
cd ~/expense-tracker
./deploy.sh
```

`deploy.sh` runs `git pull && docker compose up -d --build`. The database in `data/` is preserved across deploys because it is bind-mounted, not part of the image.

### 12.9 Useful Commands

```bash
# View live logs
docker compose logs -f

# View only app logs
docker compose logs -f app

# Restart without rebuild
docker compose restart

# Stop everything (data preserved)
docker compose down

# Check container status
docker compose ps
```
