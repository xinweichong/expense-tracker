# Automatic Expense Tracker

A privacy-first expense tracking engine that automatically captures transactions from bank emails (DBS PayLah!, UOB PayNow) and Apple Wallet notifications. Zero manual input for day-to-day tracking — just spend and review via Telegram or web dashboard.

## Key Features

- **Gmail Auto-Ingestion** — Polls DBS PayLah! and UOB PayNow transaction emails automatically
- **Apple Wallet Capture** — iOS Shortcut pushes Apple Wallet notifications to your server
- **Telegram Bot** — Real-time transaction alerts, spending queries (`/today`, `/week`, `/month`), and manual CRUD
- **Web Dashboard** — Monthly trends, category breakdowns, and merchant frequency charts
- **Auto-Categorization** — Keyword-based merchant matching with manual override
- **Privacy-First** — All data stays on your machine in SQLite. No cloud services, no third-party data sharing

## Architecture

```
Gmail API ──poll──> Parser Engine ──> SQLite <──> Telegram Bot
                       ^                ^    └──> Web Dashboard
                       │                │
iOS Shortcut ──POST──> ┘                └── Auto-categorizer
```

Single Python process. SQLite storage with WAL mode. FastAPI for webhooks and dashboard.

## Prerequisites

- Python 3.11+
- Gmail account with API credentials (for email ingestion)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- A server reachable from your iPhone (for Apple Wallet webhooks) — Tailscale, Cloudflare Tunnel, or static IP

## Installation

### 1. Clone and set up

```bash
git clone https://github.com/xinweichong/expense-tracker.git
cd expense-tracker
git checkout develop
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` and fill in:
- `telegram.bot_token` — from @BotFather
- `web.password_hash` — generate with: `python -c "import bcrypt; print(bcrypt.hashpw(b'your-password', bcrypt.gensalt()).decode())"`
- `server.webhook_base_url` — your server's reachable URL

### 3. Gmail OAuth (one-time)

```bash
python scripts/gmail_auth.py
```

Follow the browser prompt to authorize read-only Gmail access. This creates `credentials.json` and `token.json` (both gitignored).

### 4. iOS Shortcut Setup (Apple Wallet Auto-Capture)

This sets up an iOS Automation that **automatically fires** whenever an Apple Wallet transaction occurs. The Shortcut extracts transaction details (date, card, merchant, amount) and POSTs them as JSON to your server webhook.

**Prerequisite:** Your server must be reachable from your iPhone (via Tailscale, Cloudflare Tunnel, or public IP).

#### Part A: Create the Automation

1. Open the **Shortcuts** app on your iPhone
2. Go to the **Automation** tab (bottom of screen) → tap **"+"** → **"Create Personal Automation"**
3. Scroll down or search for **"Transaction"** → select it
4. **Select the cards** you want to automate
5. Leave all **categories** checked
6. Don't filter on **Merchants**
7. Select **"Run Immediately"**
8. Leave **"Notify When Run"** de-selected (off)
9. Tap **"Next"**
10. Choose **"New Blank Automation"**

You now have an empty automation that triggers on every Apple Wallet transaction. Next, add actions (approximately 14 total).

#### Part B: Date, Card, and Merchant (4-5 actions)

**Action 1 — Format the Date:**
- In the search box, type **"Format"** and choose **"Format Date"**
- Tap the **Date** box → scroll along the **Select Variable** row → choose **"Current Date"**
- Set **Date Format** to **"Custom"**
- Set the format string to `dd/MM/yyyy HH:mm:ss` (capitalization matters)
- This creates a magic variable called **"Formatted Date"**

**Action 2 — Escape quotes in Card name:**
- Add a **"Replace Text"** action
- Set the first box to `"` and the second to `\"`
- Change the variable to **Shortcut Input** → select it again → change to **"Card or Pass"** (double selection)
- This handles card/account names that contain quote characters

**Action 3 — Set Card variable:**
- Add a **"Set Variable"** action
- Set variable name to **"Card"**
- Set the value to the magic variable **"Updated Text"** (from the previous Replace Text)
- Note: if you only have one card, you can skip the Replace Text and simply set Card to your account name directly

**Action 4 — Escape quotes in Merchant:**
- Add a **"Replace Text"** action
- Set the first box to `"` and the second to `\"`
- Change the variable to **Shortcut Input** → select it again → change to **"Merchant"** (double selection)

**Action 5 — Set Merchant variable:**
- Add a **"Set Variable"** action
- Set variable name to **"Merchant"**
- Set the value to the magic variable **"Updated Text"**

#### Part C: Amount (7 actions)

The amount from Apple Wallet is **not a number** — it's text. It needs careful parsing and negation (spending should be negative, refunds positive).

**Action 6 — Strip non-numeric characters from Amount:**
- Add a **"Replace Text"** action
- Set the first box to `[^\d\.]` (or `[^\d\,]` if your region uses comma as decimal separator)
- Leave the second box **empty**
- Change the variable to **Shortcut Input** → select it again → change to **"Amount"** (double selection)
- Tap the **right arrow** → set **"Regular Expression"** to **on**

**Action 7 — Set Amount variable:**
- Add a **"Set Variable"** action
- Set variable name to **"Amount"**
- Set the value to the magic variable **"Updated Text"**

**Action 8 — Check if amount is already negative:**
- Add a **"Match Text"** action
- Set the first box to `-`
- Change the variable to **Shortcut Input** → select it again → change to **"Amount"** (double selection)
- This produces a magic variable called **"Matches"**

**Action 9 — If amount is NOT negative, negate it:**
- Add an **"If"** action
- Set the first box to the magic variable **"Matches"**
- Set the condition to **"does not have any value"**
- You can delete the **"Otherwise"** section (not needed)

**Action 10 — Prepend negative sign (inside the If block):**
- Add a **"Combine Text"** action
- Set the first box to `-`
- Set the second box to the **"Amount"** variable
- Set **"with"** to **"Custom"** and leave the separator box empty

**Action 11 — Update Amount variable (inside the If block):**
- Add a **"Set Variable"** action
- Set variable name to **"Amount"**
- Set the value to the magic variable **"Combined Text"**
- **Drag** this action and the Combine Text action (Action 10) to be between the **"If"** and **"End IF"** actions

#### Part D: Send to Server (2-3 actions)

**Action 12 — Build the JSON payload:**
- Add a **"Text"** action
- Set it to the following (replacing `Card`, `Formatted Date`, `Merchant`, and `Amount` with their actual magic variables by tapping in the text field and selecting from the variable bar above the keyboard):

```
{"card":"Card","date":"Formatted Date","merchant":"Merchant","amount":"Amount"}
```

The actual text field content should look like (with variables inserted):
```
{"card":"Card","date":"Formatted Date","merchant":"Merchant","amount":"Amount"}
```

Where each placeholder is the magic variable (highlighted in the Shortcuts editor).

**Action 13 — Send to server:**
- Add a **"Get Contents of URL"** action
- **URL field:** Enter your server URL:
  ```
  https://YOUR-SERVER-URL/webhook/apple-wallet
  ```
  (Replace with your actual server address from `config.yaml` → `server.webhook_base_url`)
- Tap **"Show More"** to expand
- **Method:** Change to **POST**
- **Headers:** Add one header:
  - Key: `Content-Type`
  - Value: `application/json`
- **Request Body:** Expand → select **"File"** → set to the magic variable **"Text"** (from Action 12)

Alternatively, you can set the Request Body to **"JSON"** and manually add each field:
  - `card` → Text → **Card** variable
  - `date` → Text → **Formatted Date** variable
  - `merchant` → Text → **Merchant** variable
  - `amount` → Text → **Amount** variable (note: this is a string, the server will parse it)

#### JSON Payload the Server Expects

```json
{
  "amount": -12.50,
  "merchant": "Toast Box",
  "card_last4": "DBS Debit",
  "date": "16/04/2026 12:30:00"
}
```

**Field details:**
- `amount` — The transaction amount as a number. **Negative for spending**, positive for refunds. The Shortcut handles negation automatically.
- `merchant` — The payee/merchant name (string). Quotes are escaped by the Shortcut.
- `card_last4` — The card/account name (string, e.g. "DBS Debit" or "UOB Visa")
- `date` — Transaction date/time as a string in `dd/MM/yyyy HH:mm:ss` format

**Required fields:** `amount`, `merchant`
**Optional fields:** `card_last4`, `date`

> **Important:** The `amount` arrives as a **string** from the Shortcut (e.g. `"-12.50"`). The server's Apple Wallet parser must convert this to a float. The server should also parse the date format `dd/MM/yyyy HH:mm:ss`.

#### Testing the Automation

1. Tap the **play** button at the bottom right of the automation to test manually
   - This won't have actual transaction details, but you can check that the JSON and URL are constructed correctly
2. Add a temporary **"Show Result"** action after the text action to inspect the JSON payload
3. For a full end-to-end test, make a real purchase with your Apple Wallet card and verify:
   - Check `logs/app.log` on the server for: `INFO: POST /webhook/apple-wallet - 200 OK`
   - Verify the transaction appears via Telegram: send `/today` to your bot
4. Expect to refine the Shortcut over the first few purchases — it typically takes ~8 real transactions to get everything working correctly

#### Troubleshooting iOS Shortcuts

| Issue | Solution |
|-------|----------|
| Automation doesn't fire | Go to **Settings → Shortcuts → Advanced → enable "Allow Running Scripts"**. Check Focus modes aren't blocking automation. Verify "Run Immediately" is selected. |
| Server returns 400 | Check the JSON payload. Add a "Show Result" action to inspect what's being sent. Verify amount is a valid number string and merchant is not empty. |
| Server unreachable from iPhone | Verify the URL works in Safari on your iPhone. Tailscale must be connected on both devices. Test with a simple GET request first. |
| Amount is wrong sign | Double-check the If/End If block — the "Combine Text" and "Set Variable Amount" actions must be *inside* the If block. Spending should be negative. |
| Amount has extra characters | Verify the regex `[^\d\.]` is set correctly and Regular Expression is turned on. Some regions use `,` as decimal separator — use `[^\d\,]` instead. |
| Merchant/Card has broken quotes | Verify the Replace Text actions for Card and Merchant are correctly escaping `"` to `\"`. |
| Duplicate transactions | The server deduplicates by `merchant + amount` within a 5-minute window — re-running won't create duplicates. |

### 5. Run

```bash
python src/main.py
```

Or install as a systemd/launchd service for auto-start on boot.

## Testing

```bash
pytest tests/ -v
```

All tests use in-memory SQLite — no database files created on disk.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Gmail auth fails | Delete `token.json` and re-run `scripts/gmail_auth.py`. Token may have expired or been revoked. |
| No transactions appearing | Check `logs/app.log` for parser errors. Verify sender filters in config match actual email senders. |
| Telegram bot not responding | Verify `bot_token` in config. Check that the bot is started (send `/start` to it in Telegram). |
| Web dashboard not loading | Check `server.port` isn't in use. Verify `web.password_hash` is a valid bcrypt hash. |
| Apple Wallet webhooks not received | Verify `webhook_base_url` is reachable from iPhone. Check server logs for incoming POST requests. |
| Duplicate transactions | `source_id` UNIQUE constraint handles deduplication. For Apple Wallet, a 5-minute window dedup is applied. |
| SQLite locked errors | WAL mode is enabled by default. If issues persist, ensure only one process accesses the DB file. |

## Git Workflow

```
feature/xxx ──merge──> develop ──test──> main (tagged release)
```

- **feature branches** — all development work
- **develop** — integration testing branch
- **main** — production releases only, each tagged with a version number

## License

Private project. All rights reserved.
