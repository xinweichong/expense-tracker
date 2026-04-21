# Transaction Details in Telegram Summaries + Web Dashboard Edit/Delete

**Date:** 2026-04-21

## Context

Telegram bot summaries (`/today`, `/week`, `/month`) currently show only category totals. Users need to see individual transactions with full details. The web dashboard displays transactions but lacks edit/delete functionality, even though the storage layer already supports these operations.

## Part 1: Telegram Bot — Transaction Details in Summaries

### Format: Detailed Multi-line

After the existing category breakdown, append individual transaction blocks:

```
#42 | 2026-04-21
Toast Box · Food
$12.50 SGD
Source: uob-card

#39 | 2026-04-21
7-Eleven · Food
$3.72 SGD (THB 100.00)
Source: cash
```

Each block shows: ID, date, merchant, category, amount in SGD, original currency/amount if foreign, source.

### Message splitting

Telegram enforces a 4096-char limit per message. When formatted content exceeds ~3800 chars, split into sequential messages and `reply_text` each one.

### Files to modify

- `src/telegram_bot.py`
  - New `_format_tx_block(tx)` — formats a single transaction dict into a multi-line string
  - New `_send_long_message(update, text, parse_mode)` — splits and sends sequentially
  - Update `format_daily_summary()` — query transactions for the date, append blocks after category totals
  - Update `format_weekly_summary()` — same pattern with date range
  - Update `_month()` — same pattern with month date range

### Existing code to reuse

- `storage.query_transactions(start_date, end_date)` — already returns list of transaction dicts with all fields

## Part 2: Web Dashboard — Edit/Delete Transactions

### Backend API

New endpoints in `src/web/app.py`, all behind `require_auth`:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/transactions/{tx_id}` | Fetch single transaction |
| PUT | `/api/transactions/{tx_id}` | Update transaction fields |
| DELETE | `/api/transactions/{tx_id}` | Delete transaction |

**PUT** accepts JSON body with any of: `merchant`, `amount`, `currency`, `exchange_rate`, `category`, `description`, `transaction_date`, `type`. Validates transaction exists.

**DELETE** validates existence, then hard-deletes.

### Existing code to reuse

- `storage.get_transaction(tx_id)` — fetch single transaction
- `storage.update_transaction(tx_id, **fields)` — partial update
- `storage.delete_transaction(tx_id)` — hard delete

### Frontend — Transaction Action Buttons

Each transaction row gets edit (pencil) and delete (trash) icon buttons.

- **Desktop**: visible on hover (CSS `:hover` on `.tx-item`)
- **Mobile**: always visible (no hover state), sized for touch targets (min 36px tap area)

### Frontend — Edit Modal

Centered modal overlay with form fields:

- Merchant (text input)
- Amount (number input) + Currency (text input, default SGD)
- Category (dropdown, populated from `/api/categories`)
- Date (date input)
- Save and Cancel buttons

Styling matches existing dark fintech theme (`--bg-surface`, `--bg-card`, `--border`, `--accent`).

On save: `PUT /api/transactions/{id}`, refresh transaction list, close modal.

### Frontend — Delete Confirmation

Confirmation dialog: "Delete transaction #42 — Toast Box ($12.50)?" with Cancel/Confirm buttons.

On confirm: `DELETE /api/transactions/{id}`, refresh transaction list, close dialog.

### Files to modify

- `src/web/app.py` — add 3 new API endpoints
- `src/web/static/index.html` — add modal HTML
- `src/web/static/dashboard.js` — add action buttons, modal open/close, API calls, list refresh
- `src/web/static/style.css` — add modal styles, action button styles, mobile overrides

## Verification

1. Run bot, send `/today` / `/week` / `/month` — verify individual transactions appear with full details after category summary
2. Open web dashboard, verify edit/delete buttons on transaction rows (hover on desktop, always visible on mobile)
3. Click edit — modal opens pre-filled, save updates transaction
4. Click delete — confirmation appears, confirm removes transaction
5. Run `pytest tests/` — no regressions
