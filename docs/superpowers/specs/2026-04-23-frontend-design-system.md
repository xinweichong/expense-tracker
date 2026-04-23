# Frontend Design System Spec

## Problem

Design tokens (colors, spacing, border styles) and Recharts configuration are
duplicated across ~15 files with no single source of truth. Every new card added
without knowing the convention ships with a white border or the wrong background.
Color values for income/expense differ between the chart and the CSS token.
Tooltip, axis, and legend config is copy-pasted across all five chart components.

## Goal

Introduce a three-layer design system that makes correct usage the path of least
resistance and ensures a change to one token propagates everywhere automatically.

---

## Layer 1 — CSS (`index.css` + `card.tsx`)

### `card.tsx` changes

- Tighten padding defaults: `CardHeader`, `CardContent`, `CardFooter` from `p-6` → `p-4`.
  `CardHeader` additionally drops the default `space-y-1.5` to `space-y-1`.
- Add `border-border` to the Card base class so a bare `<Card>` always gets the
  dark `#2A2A32` border. No consumer needs to remember `border-border` ever again.

  New base: `"rounded-lg border border-border bg-card text-card-foreground shadow-sm"`

### `index.css` additions (`@layer components`)

Two utility classes covering the two scattered form/button patterns:

```css
@layer components {
  .input-field {
    @apply px-3 py-1.5 text-sm bg-background border border-border rounded-md text-foreground;
  }
  .btn-action {
    @apply px-4 py-1.5 text-sm bg-foreground text-background rounded-md hover:opacity-90;
  }
}
```

**`.input-field`** replaces the repeated `px-3 py-1.5 text-sm bg-background border border-border rounded-md` on native `<input>` elements in `SettingsPage` and `TransactionFilters`.

**`.btn-action`** replaces the raw `<button>` Save style in `SettingsPage`.

---

## Layer 2 — Chart constants (`src/lib/chartTheme.ts`)

A single TypeScript module exporting all Recharts configuration objects and data
colors. Chart components import from here; no Recharts props are hardcoded inline.

### Exports

```ts
// Tooltip
CHART_TOOLTIP_STYLE: CSSProperties
// { background: '#16161A', border: '1px solid #2A2A32', borderRadius: '8px', fontSize: '13px' }

// Axis (spread onto XAxis / YAxis)
CHART_AXIS_PROPS: Partial<XAxisProps & YAxisProps>
// { tick: { fontSize: 11, fill: '#72727E' }, tickLine: false, axisLine: false }

// Tooltip cursor variants
CHART_CURSOR_BAR: object   // { fill: '#1C1C22' }
CHART_CURSOR_LINE: object  // { stroke: '#2A2A32', strokeWidth: 1 }

// Legend
CHART_LEGEND_STYLE: CSSProperties
// { fontSize: '12px', color: '#72727E' }

// Data colors — aligned to CSS tokens
COLOR_INCOME:    '#30D158'   // matches --color-success
COLOR_EXPENSE:   '#FF453A'   // matches --color-destructive
COLOR_ACCENT:    '#00D4AA'   // matches --color-accent (trend lines, current-period bars)
COLOR_MUTED_BAR: '#3A3A46'   // previous-period bars in ComparisonBarChart
```

### Alignment fixes

- `IncomeExpenseBar` currently uses `#22c55e` (income) and `#ef4444` (expense) —
  neither matches the CSS tokens. Both are corrected to `COLOR_INCOME`/`COLOR_EXPENSE`.

---

## Layer 3 — Wrapper components (`src/components/ui/cards.tsx`)

Three composable card wrappers built on top of the existing `Card` / `CardHeader` /
`CardContent` primitives. Consumers never touch the primitives directly for standard
usage; they use the wrappers.

### `<PageCard>`

Standard content card. Enforces `CardHeader` + `CardContent` structure.

```tsx
interface PageCardProps {
  title: string
  action?: React.ReactNode   // rendered right-aligned in the header (e.g. toggle buttons)
  children: React.ReactNode
  className?: string         // forwarded to Card root for one-off overrides
}
```

Renders:
```tsx
<Card className={cn(className)}>
  <CardHeader className="flex flex-row items-center justify-between">
    <CardTitle className="text-base font-medium">{title}</CardTitle>
    {action}
  </CardHeader>
  <CardContent>{children}</CardContent>
</Card>
```

**Used for:** Category donut card, Trend line card, Transactions card (Overview);
Period Comparison, Spending Velocity, Top Merchants (Analytics); transaction list
(Transactions); Categories, Alert Thresholds, Merchant Overrides (Settings).

### `<ChartCard>`

Like `PageCard` but `CardContent` has zero padding so charts can render edge-to-edge.

```tsx
interface ChartCardProps {
  title: string
  action?: React.ReactNode
  children: React.ReactNode
  className?: string
}
```

Renders identically to `PageCard` except `CardContent` gets `className="p-0"`.

**Used for:**
- `IncomeExpenseBar` uses `ChartCard` internally (it is a self-contained component
  that owns its own data fetching and card wrapper).
- `AnalyticsPage` uses `ChartCard` for the Period Comparison slot (wraps
  `ComparisonBarChart` at the page level; the badge goes in the `action` prop).
- `AnalyticsPage` uses `PageCard` for Spending Velocity (VelocityRing is an SVG,
  not a Recharts chart, so edge-to-edge rendering is not needed).
- `AnalyticsPage` uses `PageCard` for Top Merchants (table, not a chart).

### `<StatCard>`

Compact two-line card for numeric KPIs.

```tsx
interface StatCardProps {
  label: string
  value: string
  variant?: 'expense' | 'income' | 'neutral'  // controls value text color
}
```

Renders:
```tsx
<Card>
  <CardHeader className="pb-1">
    <CardTitle className="text-sm font-medium text-muted">{label}</CardTitle>
  </CardHeader>
  <CardContent>
    <p className={cn('text-2xl font-bold', variantClass)}>{value}</p>
  </CardContent>
</Card>
```

Variant → class mapping: `expense → text-destructive`, `income → text-success`,
`neutral → text-foreground`.

**Used for:** Spent / Income balance cards in `OverviewPage`.

### What is NOT abstracted

- **Alert card** (`AnalyticsPage`) — intentionally uses `border-warning/30`, unique
  semantics. Keep bespoke.
- **Login card** (`LoginScreen`) — unique layout, not a repeating pattern.
- **`TransactionRow`** — the hex-alpha string concatenation (`${color}1A` etc.) is
  left as-is; it is a separate concern from the card/chart design system.

---

## Migration Map

| File | Changes |
|---|---|
| `src/components/ui/card.tsx` | Tighten padding defaults; add `border-border` to base |
| `src/index.css` | Add `.input-field` and `.btn-action` under `@layer components` |
| `src/lib/chartTheme.ts` | **New file** — all chart constants |
| `src/components/ui/cards.tsx` | **New file** — `PageCard`, `ChartCard`, `StatCard` |
| `src/pages/OverviewPage.tsx` | Use `StatCard`, `PageCard` (donut, trend, transactions) |
| `src/pages/AnalyticsPage.tsx` | Use `PageCard`/`ChartCard` for all four cards |
| `src/pages/TransactionsPage.tsx` | Use `PageCard` for transaction list |
| `src/pages/SettingsPage.tsx` | Use `PageCard` for all cards; `.input-field`, `.btn-action` |
| `src/components/charts/TrendLine.tsx` | Use `CHART_AXIS_PROPS`, `CHART_TOOLTIP_STYLE`, `CHART_CURSOR_LINE` |
| `src/components/charts/CategoryTrendLine.tsx` | Use `CHART_AXIS_PROPS`, `CHART_TOOLTIP_STYLE`, `CHART_CURSOR_LINE`, `CHART_LEGEND_STYLE` |
| `src/components/charts/ComparisonBarChart.tsx` | Use `CHART_AXIS_PROPS`, `CHART_TOOLTIP_STYLE`, `CHART_CURSOR_BAR`, `CHART_LEGEND_STYLE`, `COLOR_ACCENT`, `COLOR_MUTED_BAR` |
| `src/components/charts/IncomeExpenseBar.tsx` | Use `CHART_AXIS_PROPS`, `CHART_TOOLTIP_STYLE`, `CHART_CURSOR_BAR`, `CHART_LEGEND_STYLE`, `COLOR_INCOME`, `COLOR_EXPENSE`; use `ChartCard` |
| `src/components/charts/CategoryDonut.tsx` | Use `CHART_TOOLTIP_STYLE` |
| `src/components/transactions/TransactionFilters.tsx` | Apply `.input-field` to date inputs |

---

## Non-Goals

- Redesigning any existing visual appearance (colors, layout, chart types)
- Changing `TransactionRow`'s hex-alpha opacity pattern
- Extracting `AlertCard` into a wrapper component
- Touching backend code
