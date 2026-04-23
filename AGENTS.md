# AGENTS.md — AI Agent Context

## Project Overview

Automatic Expense Tracker — a privacy-first Python service that ingests transaction data from Gmail (DBS PayLah!, UOB PayNow) and Apple Wallet push notifications, stores them in SQLite, and provides interaction via Telegram bot and a web dashboard.

## Architecture

Single Python monolith, one process, six subsystems:
1. **Gmail Poller** — scheduled polling of Gmail API for transaction emails, HTML body extraction fallback
2. **Webhook Receiver** — FastAPI endpoint receiving Apple Wallet data from iOS Shortcuts, cross-source dedup
3. **Parser Engine** — plugin-based bank/payment parsers (one class per source)
4. **Interaction Layer** — Telegram bot (commands + notifications + guided UX) + Web dashboard (dark fintech theme, Recharts)
5. **Categorization** — keyword matching + learned merchant overrides, with match source tracking
6. **Intelligence** — recurring transaction detection, spending insights, multi-currency exchange rates

All data in SQLite with WAL mode. Single-user, single-password system. Supports income and expense tracking.

## Agent Instructions

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

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

## Backend Conventions

### Storage Layer

- Every expense-only query uses `(type IS NULL OR type = 'expense')` — never just `type = 'expense'`. Pre-migration rows have a NULL type and are silently dropped otherwise.
- All mutating methods (`update_transaction`, `delete_transaction`, `update_category`, `delete_category`) pre-check existence and raise `ValueError("<entity> not found")` on miss. The API layer catches `ValueError` and returns HTTP 404. Never raise `HTTPException` from Storage.
- `delete_category` cascades: reassigns all affected transactions to `'Other'` and deletes matching `merchant_overrides`. Returns the reassigned count, surfaced as `{"status": "ok", "reassigned": count}` in the API.
- `app_settings` stores all values as `TEXT`. Always cast to `float`/`int` at the call site. `set_setting` always receives `str(val)`.
- `ingestion_state` is dual-purpose: Gmail poller state (keyed by source name, e.g. `"dbs_paylah"`) and the Telegram chat ID (stored under `source='telegram_chat_id'`, value in `last_processed_id`).
- `get_categories` orders by `ROWID` (insertion order) — this controls the Telegram inline keyboard order and dashboard dropdown order.
- Default settings use `INSERT OR IGNORE` (preserved after first write). Categories use `INSERT OR REPLACE` on every startup — user-modified keywords in the DB are reset on restart.
- `get_trend_by_category` explicitly sets missing-category keys to `None` (not `0` or absent) for Recharts `connectNulls`. Do not substitute `0` or omit the key.
- The allowed-field whitelist for `update_transaction` is enforced in `web/app.py`, not in `Storage`. Add new editable columns to the `allowed` set in `app.py`.
- `query_transactions` default limit is 100; the API layer defaults to 50; CSV export hard-codes 50,000. Always pass explicit limits in new callers.

### API Layer

- `require_auth` is `Depends(require_auth)` added to each route individually — there is no global auth middleware. Forgetting it on a new route silently makes it public.
- All responses are raw `dict`/`list` — no Pydantic response models. All DB columns including `raw_data` and `ingested_at` are returned to the client.
- `PUT /api/transactions/{id}` auto-calls `storage.set_merchant_override()` when the category changes, but does not call `categorizer.reload_overrides()` — the web API holds no categorizer reference.
- `PUT /api/settings` is all-or-nothing: validates all fields, collects errors into a dict, raises HTTP 422 with the errors dict, or writes all values atomically. Never writes a partial update.
- Manual transactions via the web API use `source_id = f"manual_{uuid4().hex[:12]}"`. Telegram `/add` uses `f"manual-{timestamp}-{amount}"`. Both use `source="manual"` and coexist in the DB.
- The SPA catch-all `/{full_path:path}` is only registered at startup if `src/web/dist/` exists. If the frontend is not built, all non-API paths return 404.

### Parser System

- Email parsers return `None` on non-match. `AppleWalletParser.parse()` raises `ValueError` on missing required fields (caught by the webhook route and converted to HTTP 400). The Gmail poller does not expect parser exceptions.
- `source_id` construction strategy per parser:

| Parser | Strategy |
|--------|----------|
| `dbs_paylah` | DBS "Transaction Ref" field from email |
| `uob_paynow` | `sha256(full_body)[:16]` |
| `uob_card` | `sha256(date:amount:merchant:card_last4)[:16]` |
| `apple_wallet` | `sha256(merchant:amount::date)[:16]` — double colon is intentional (empty card-field slot for backward compat) |
| web manual | `manual_{uuid4().hex[:12]}` |
| bot `/add`, `/cash` | `manual-{YYYYMMDDHHMMSS}-{amount}` |

- Apple Wallet hash uses `f"{merchant}:{amount}::{date}"` — the double colon is a deliberate empty card-field slot for backward compatibility with pre-card-name records. Do not add the card field into this hash.
- Currency parsing precedence: ISO code prefix (`PLN 3.78`) → multi-char symbols (`S$`, `A$`, `HK$`, `RM`...) → single-char symbols (`£`, `€`...) → bare number defaults to SGD. Multi-char must be checked before single-char to avoid `S$` matching as `$`.
- DBS PayLah! infers `datetime.now().year` because the email format omits the year. A December email processed in January will have the wrong year — this is a known limitation.

### Telegram Bot

- The bot silently drops all outbound notifications until `/start` is sent at least once (the chat ID is registered by `/start` into `ingestion_state`).
- `notify_transaction` and `notify_text` use `asyncio.run_coroutine_threadsafe(..., self._loop)` to bridge from the Gmail/APScheduler threads into the bot's asyncio event loop. Never use `await` or `asyncio.run()` in these methods.
- Callback data is namespaced by prefix: `cat:` (new tx category pick), `recat:` (recategorize), `ef_` (edit field), `ec_` (edit category), `cmd_` (menu actions), `confirm_delete_` / `cancel_delete`. Handler registration order matters.
- `/add` and `/cash` only extract a category if a date is also present. Format: `<amount> [currency] <merchant> [category] <date>`.
- `/income` stores the description in the `merchant` column (not `description`), hard-codes `category="Income"` and `type="income"`, and skips the categorizer.
- `_cmd_callback` uses a `SimpleNamespace` / `_ReplyProxy` to let inline button presses re-use existing command handlers without modification.

### Cross-Cutting Rules

- Always use `local_now()` from `src/config.py` for wall-clock dates. Never use `datetime.now()` or `datetime.utcnow()` — Railway runs UTC and this caused `/today` to show the wrong day for SGT users (fixed in commit `eeed856`). `local_now()` defaults to `Asia/Singapore`; configurable via `timezone:` in `config.yaml` or `TIMEZONE` env var.
- `transaction_date` is stored as ISO 8601 string `"YYYY-MM-DDTHH:MM:SS"`. Range queries must use `DATE(transaction_date) >= ?`. Display truncates to `[:10]`.
- `raw_data` for Apple Wallet transactions is `str(dict)` (Python `repr`), not valid JSON. Re-parsing requires `ast.literal_eval`, not `json.loads`.
- DB path resolution: `EXPENSE_DB_PATH` env var → `/data/expense_tracker.db` if `/data/` exists (Railway volume) → `expense_tracker.db` in CWD. Connection uses `check_same_thread=False` (shared across threads).
- Migrations in `init_db` wrap each `ALTER TABLE` in bare `except: pass` — SQLite has no `ADD COLUMN IF NOT EXISTS`. All new column migrations must follow this pattern.
- `RecurringDetector` only runs on the webhook ingestion path, not Gmail. It looks back 90 days and is instantiated per-call (stateless).
- The `source` column has no `CHECK` constraint — invalid values insert silently. Valid values: `dbs_paylah`, `uob_paynow`, `uob_card`, `apple_wallet`, `manual`, `cash`.
- `Storage` has no `logging` import — it is a pure data layer. All logging lives in the service layer.

### Testing Conventions

- The schema in `tests/conftest.py` `in_memory_db` fixture must mirror the fully-migrated schema in `main.py init_db`. When adding a migration column in `main.py`, also add it to the `conftest.py` schema string.
- There is no shared `Storage` or `Categorizer` fixture — tests instantiate them inline: `Storage(in_memory_db)`.
- `sample_categories` fixture uses comma-separated string keywords (`"restaurant,cafe,food"`). `sample_config` uses Python lists. Both mirror real usage: Storage receives the comma-separated string form; Categorizer receives the list form from YAML.

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

## Frontend UI Design System

### Tech Stack

React 19 + TypeScript + Vite. Tailwind CSS v4 (`@theme` block in `index.css` — no config file). Recharts for all charts. Radix UI primitives (Dialog, Select, DropdownMenu, Tabs, Separator, Slot). shadcn/ui component patterns with CVA (class-variance-authority). lucide-react for all icons. TanStack Query for server state. Frontend root: `src/web/frontend/src/`.

### Color Tokens

Defined in `src/web/frontend/src/index.css` under `@theme`. These become both CSS custom properties and Tailwind utility classes.

| Token | Hex | Role |
|---|---|---|
| `--color-background` | `#0D0D0F` | Page background |
| `--color-card` | `#16161A` | Card surfaces, tooltip background |
| `--color-card-hover` | `#1C1C22` | Bar chart hover cursor |
| `--color-border` | `#2A2A32` | All borders and dividers |
| `--color-foreground` | `#E8E8ED` | Primary text |
| `--color-muted` | `#72727E` | Secondary text, axis ticks, labels |
| `--color-accent` / `--color-primary` | `#00D4AA` | CTAs, active states, trend lines, current-period bars |
| `--color-primary-foreground` | `#0D0D0F` | Text on accent background |
| `--color-destructive` | `#FF453A` | Delete actions, error messages, overspend alerts |
| `--color-success` | `#30D158` | Income amounts, "on track" status |
| `--color-warning` | `#FFD60A` | Unusual spending alerts |
| `--color-info` | `#64D2FF` | Informational, "under pace" velocity |

**Semantic color rules — these have caused real bugs, apply carefully:**
- `text-destructive` for delete buttons, error messages, and "spending ahead of pace" — **never `text-accent`**. Using `text-accent` on destructive actions was a bug fixed across multiple files in `859dd5e`.
- `text-warning` for unusual spending alert icons and borders — **never `text-accent`**. Fixed in `ace89a3`.
- `text-accent` is only for primary interactive states, active toggle buttons, and chart lines/bars. The accent color was changed from `#FF6B6B` to teal specifically to stop it clashing with the Food category color (`29f259c`).
- `text-success` for income amounts and positive spending velocity.
- `text-info` for neutral informational status ("under pace").

### Category Color System

`getCategoryColor(category)` in `src/lib/utils.ts` — always use this function, never hardcode category colors. Runtime overrides (learned via recategorization) are loaded into `_categoryColorOverrides` via `setCategoryColors()`.

**Hex-suffix opacity convention** for category row tinting — must be consistent across all transaction lists:
- Row background resting: `${categoryColor}0D` (5% opacity)
- Row background hover: `${categoryColor}1A` (10% opacity)
- Icon pill background: `${categoryColor}33` (20% opacity)
- Edit mode active background: `${categoryColor}1A`

The 20-color `PALETTE` array in `lib/utils.ts` is used by the category color picker in Settings. The picker enforces uniqueness — already-used colors are shown at 30% opacity and are non-interactive.

### Chart Conventions

All Recharts configuration is centralized in `src/lib/chartTheme.ts`. **Never inline Recharts props** — import from `chartTheme.ts`. This is necessary because Recharts does not support CSS custom properties, so hex values are encoded in named constants rather than scattered across components.

| Export | Apply to |
|---|---|
| `CHART_TOOLTIP_STYLE` | `<Tooltip contentStyle={CHART_TOOLTIP_STYLE}>` |
| `{...CHART_AXIS_PROPS}` | Spread onto every `<XAxis>` and `<YAxis>` |
| `CHART_CURSOR_BAR` | `<Tooltip cursor={CHART_CURSOR_BAR}>` on BarCharts |
| `CHART_CURSOR_LINE` | `<Tooltip cursor={CHART_CURSOR_LINE}>` on LineCharts |
| `CHART_LEGEND_STYLE` | `<Legend wrapperStyle={CHART_LEGEND_STYLE}>` |
| `COLOR_ACCENT` | `#00D4AA` — trend lines, current-period bars |
| `COLOR_MUTED_BAR` | `#3A3A46` — previous-period bars in ComparisonBarChart |
| `COLOR_INCOME` | `#30D158` — matches `--color-success` |
| `COLOR_EXPENSE` | `#FF453A` — matches `--color-destructive` |

Note: `COLOR_INCOME` and `COLOR_EXPENSE` were previously `#22c55e` / `#ef4444` (Tailwind defaults), which did not match the CSS tokens. Both were corrected in the design system commit.

### Card Component System

Three tiers — use the highest applicable tier, not the lower primitives directly.

**Tier 1 — Base `Card` (from `src/components/ui/card.tsx`):**
`border-border` is baked into the base class. Never add `border-border` or `bg-card` explicitly to a `<Card>` — they are redundant. Padding defaults: `CardHeader` `p-4`, `CardContent` `p-4 pt-0`.

**Tier 2 — Wrapper components (from `src/components/ui/cards.tsx`):**

| Component | Use for | Key difference |
|---|---|---|
| `PageCard` | Content, tables, lists, SVG-based visuals | `CardContent` retains `p-4` padding |
| `ChartCard` | Recharts chart components | `CardContent className="p-0"` — charts render edge-to-edge |
| `StatCard` | Compact numeric KPI display | Props: `label`, `value`, `variant` (`'expense'`/`'income'`/`'neutral'`) |

All three accept `title`, `children`, and optional `action` (rendered right-aligned in the header, e.g. toggle buttons, badges). `className` is forwarded to the Card root for one-off overrides.

**Tier 3 — Bespoke (use raw `Card`):**
- Alert card in Analytics — `border-warning/30` semantics, intentionally not abstracted
- Login card — unique layout, not a repeating pattern

`TransactionRow`'s hex-alpha opacity tinting is a separate concern — do not apply `PageCard`/`ChartCard` there.

### CSS Utility Classes

Utility classes defined in `src/web/frontend/src/index.css` under `@layer components`:

- **`.input-field`** — use on native `<input>` elements: `px-3 py-1.5 text-sm bg-background border border-border rounded-md text-foreground`. Replaces the repeated inline string.
- **`.btn-action`** — use for primary save/submit `<button>` elements outside the Button CVA system: `px-4 py-1.5 text-sm bg-foreground text-background rounded-md hover:opacity-90`.
- **`.select-field`** — use on all native `<select>` elements. Includes the white SVG chevron via `background-image`. Never use `.input-field` on a `<select>`.
- **Radix `<SelectTrigger>` chevron** — always `opacity-50` (`<ChevronDown className="h-4 w-4 opacity-50" />`). Do not change to `text-foreground` or any explicit color. The 50% opacity is intentional and must be preserved across all usages.

### Navigation Pattern

Sidebar (`hidden md:flex`, `w-56` md / `w-64` lg, `sticky top-0 h-screen`, `bg-card border-r border-border`) + bottom tabs (`md:hidden fixed bottom-0 h-16`, `bg-card border-t border-border`). Main content always has `pb-20 md:pb-0` for bottom-tab clearance.

Nav item states: active `bg-foreground/10 text-foreground font-medium`, inactive `text-muted hover:text-foreground hover:bg-foreground/5`. Four routes: Overview `/`, Transactions `/transactions`, Analytics `/analytics`, Settings `/settings`.

### Common UI Patterns

- **Quick-select chips:** `px-2.5 py-1 text-xs rounded-full border transition-colors`. Active: `border-foreground text-foreground bg-foreground/10`. Inactive: `border-border text-muted hover:text-foreground`. "All time" chip is never highlighted active.
- **Segmented / inline toggle:** Container `flex rounded-md border border-border overflow-hidden`. Active button: `bg-primary text-primary-foreground`. Inactive: `text-muted hover:text-foreground`. Subsequent buttons add `border-l border-border`.
- **Source labels:** Use the `SOURCE_LABELS` map in `TransactionRow.tsx` for human-readable source display names. Never hardcode source strings in UI text.
- **Error feedback:** Always `text-sm text-destructive`, inline below the relevant field or immediately below the submit button.
- **Loading state:** Replace button label text (e.g. "Saving…"). Never leave the button without visual feedback during async operations.

### Icons & Typography

All icons from **lucide-react**. Three sizes: `w-3.5 h-3.5` inline actions (Pencil, Trash2), `w-4 h-4` standard buttons and form icons, `w-5 h-5` navigation. Category avatars use the emoji from the `icon` DB column, rendered inside a colored `div` (not an `<img>`).

**Edit/delete icon buttons — use this pattern everywhere, no exceptions:**
```tsx
<Button variant="ghost" size="icon" className="h-7 w-7" onClick={onEdit}>
  <Pencil className="w-3.5 h-3.5" />
</Button>
<Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={onDelete}>
  <Trash2 className="w-3.5 h-3.5" />
</Button>
```
- Always use `Button` from `@/components/ui/button` — never a bare `<button>` for icon actions
- Always `variant="ghost" size="icon" className="h-7 w-7"`
- Edit button: no extra color class (inherits default muted ghost style)
- Delete button: always `text-destructive` — **never `text-muted`**, **never hidden on hover**
- Icons are always **persistent** — never `opacity-0 group-hover:opacity-100` or similar reveal patterns

Size scale: `text-xs` labels/metadata, `text-sm` body/button labels, `text-base` default inputs, `text-lg` card titles, `text-xl` page headings, `text-2xl` main figures and balance amounts. Weights: `font-medium` labels/nav items, `font-semibold` card titles/amounts, `font-bold` page h1s/balance figures.

Responsive breakpoints: `sm` (640px) form layout changes, `md` (768px) sidebar visible / bottom tabs hidden / padding increases, `lg` (1024px) wider sidebar / two-column analytics grid.

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
- **Adding a category color:** Add the color to `getCategoryColor()` defaults and the 20-color `PALETTE` array in `src/web/frontend/src/lib/utils.ts`
- **Adding a new chart component:** Create in `src/components/charts/`. Import all Recharts config from `src/lib/chartTheme.ts`. Wrap in `ChartCard` from `src/components/ui/cards.tsx` if the component owns its card.
- **Adding a new page section:** Use `PageCard` (content/tables/lists) or `ChartCard` (Recharts charts) from `src/components/ui/cards.tsx`. Avoid bare `Card/CardHeader/CardContent` for standard layouts.
