import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, CalendarDays } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePeriod, type Period } from '@/hooks/usePeriod';
import { useSummary, useTrend, useTrendByCategory, useBalance } from '@/hooks/useCategories';
import { useTransactions } from '@/hooks/useTransactions';
import type { Transaction } from '@/api/client';
import { formatCurrency, formatDate, getCategoryColor, cn } from '@/lib/utils';
import { CategoryDonut } from '@/components/charts/CategoryDonut';
import { TrendLine } from '@/components/charts/TrendLine';
import { CategoryTrendLine } from '@/components/charts/CategoryTrendLine';
import { TransactionRow } from '@/components/transactions/TransactionRow';
import { StatCard, PageCard } from '@/components/ui/cards';

function toDateStr(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function getDateRange(date: string, period: Period): { start: string; end: string } {
  const [y, m, dd] = date.split('-').map(Number);
  const d = new Date(y, m - 1, dd);
  if (period === 'day') {
    return { start: date, end: date };
  }
  if (period === 'week') {
    const dayOfWeek = d.getDay();
    const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    const monday = new Date(d);
    monday.setDate(d.getDate() + mondayOffset);
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { start: toDateStr(monday), end: toDateStr(sunday) };
  }
  // month
  const first = new Date(d.getFullYear(), d.getMonth(), 1);
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return { start: toDateStr(first), end: toDateStr(last) };
}

function getRangeLabel(date: string, period: Period): string {
  const [y, m, dd] = date.split('-').map(Number);
  const d = new Date(y, m - 1, dd);
  if (period === 'day') {
    return d.toLocaleDateString('en-SG', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  }
  if (period === 'week') {
    const { start, end } = getDateRange(date, period);
    return `${formatDate(start)} - ${formatDate(end)}`;
  }
  return d.toLocaleDateString('en-SG', { month: 'long', year: 'numeric' });
}

const PERIOD_OPTIONS: Period[] = ['day', 'week', 'month'];

export function OverviewPage() {
  const { period, setPeriod, date, goBack, goForward, goToToday } = usePeriod();
  const { start, end } = useMemo(() => getDateRange(date, period), [date, period]);
  const [trendMode, setTrendMode] = useState<'total' | 'category'>('total');

  const { data: summary } = useSummary(start, end);
  const { data: trend } = useTrend(start, end);
  const { data: trendByCategory } = useTrendByCategory(start, end);
  const { data: balance } = useBalance(start, end);
  const { data: recentTransactions } = useTransactions({ start_date: start, end_date: end, limit: 50 });

  // API returns { by_category: { "Food": 50, ... } } — transform to array
  const categories = useMemo(() => {
    const byCat = summary?.by_category;
    if (!byCat || typeof byCat !== 'object') return [];
    return Object.entries(byCat).map(([category, total]) => ({ category, total: total as number }));
  }, [summary]);
  const trendData = trend ?? [];
  const trendByCategoryData = trendByCategory ?? [];
  const income = balance?.income ?? 0;
  const expenses = balance?.expenses ?? 0;

  const trendToggle = (
    <div className="flex rounded-md border border-border overflow-hidden">
      <button
        onClick={() => setTrendMode('total')}
        className={cn(
          'px-2.5 py-1 text-xs transition-colors',
          trendMode === 'total'
            ? 'bg-primary text-primary-foreground'
            : 'text-muted hover:text-foreground',
        )}
      >
        Total
      </button>
      <button
        onClick={() => setTrendMode('category')}
        className={cn(
          'px-2.5 py-1 text-xs transition-colors border-l border-border',
          trendMode === 'category'
            ? 'bg-primary text-primary-foreground'
            : 'text-muted hover:text-foreground',
        )}
      >
        By Category
      </button>
    </div>
  );

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-4xl mx-auto">
      {/* Period Selector */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">Overview</h1>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={goBack}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="sm" onClick={goToToday} className="gap-1.5 text-sm">
            <CalendarDays className="h-3.5 w-3.5" />
            Today
          </Button>
          <Button variant="ghost" size="icon" onClick={goForward}>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted min-w-[140px] text-center">{getRangeLabel(date, period)}</span>
        </div>
        <div className="flex rounded-lg border border-border overflow-hidden">
          {PERIOD_OPTIONS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={cn(
                'px-3 py-1.5 text-sm capitalize transition-colors',
                period === p
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted hover:text-foreground hover:bg-accent',
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Balance Cards */}
      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Spent" value={formatCurrency(expenses)} variant="expense" />
        <StatCard label="Income" value={formatCurrency(income)} variant="income" />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Category Donut */}
        <PageCard title="Spending by Category">
          {categories.length > 0 ? (
            <>
              <CategoryDonut data={categories} />
              <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1.5">
                {categories.map((c: { category: string; total: number }) => (
                  <div key={c.category} className="flex items-center gap-2 text-sm">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: getCategoryColor(c.category) }}
                    />
                    <span className="truncate text-muted">{c.category}</span>
                    <span className="ml-auto font-medium">{formatCurrency(c.total)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-48 flex items-center justify-center text-muted text-sm">
              No spending data for this period
            </div>
          )}
        </PageCard>

        {/* Trend Line */}
        <PageCard title="Daily Spending Trend" action={trendToggle}>
          {trendMode === 'total'
            ? <TrendLine data={trendData} />
            : <CategoryTrendLine data={trendByCategoryData} />
          }
        </PageCard>
      </div>

      {/* Transactions */}
      <PageCard title="Transactions">
        {!recentTransactions || recentTransactions.length === 0 ? (
          <p className="text-muted text-sm py-4 text-center">No transactions in this period</p>
        ) : (
          <div className="flex flex-col -mx-4">
            {recentTransactions.map((tx: Transaction) => (
              <TransactionRow key={tx.id} tx={tx} readOnly />
            ))}
          </div>
        )}
      </PageCard>
    </div>
  );
}
