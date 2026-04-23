import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { api } from '@/api/client';
import { ChartCard } from '@/components/ui/cards';
import {
  CHART_AXIS_PROPS,
  CHART_TOOLTIP_STYLE,
  CHART_CURSOR_BAR,
  CHART_LEGEND_STYLE,
  COLOR_INCOME,
  COLOR_EXPENSE,
} from '@/lib/chartTheme';

function formatMonth(month: string): string {
  // "2026-04" → "Apr"
  const [year, m] = month.split('-');
  return new Date(Number(year), Number(m) - 1, 1).toLocaleString('default', { month: 'short' });
}

const TITLE = 'Income vs Expenses — Last 6 Months';

export function IncomeExpenseBar() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['income-vs-expense'],
    queryFn: () => api.getIncomeVsExpense(6),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <ChartCard title={TITLE}>
        <div className="p-4 h-64 flex items-center justify-center text-muted text-sm">Loading…</div>
      </ChartCard>
    );
  }

  if (isError) {
    return (
      <ChartCard title={TITLE}>
        <div className="p-4 h-64 flex items-center justify-center text-muted text-sm">Failed to load data</div>
      </ChartCard>
    );
  }

  if (!data || data.length === 0) return null;

  const chartData = data.map((d) => ({
    month: formatMonth(d.month),
    Income: d.income,
    Expenses: d.expenses,
  }));

  return (
    <ChartCard title={TITLE}>
      <div className="p-4 w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <XAxis
              dataKey="month"
              {...CHART_AXIS_PROPS}
            />
            <YAxis
              {...CHART_AXIS_PROPS}
              tickFormatter={(v: number) => `$${v}`}
            />
            <Tooltip
              cursor={CHART_CURSOR_BAR}
              contentStyle={CHART_TOOLTIP_STYLE}
              formatter={(value) => value != null
                ? `$${Number(value).toLocaleString('en-SG', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
                : ''}
            />
            <Legend wrapperStyle={CHART_LEGEND_STYLE} />
            <Bar dataKey="Income" fill={COLOR_INCOME} radius={[4, 4, 0, 0]} />
            <Bar dataKey="Expenses" fill={COLOR_EXPENSE} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </ChartCard>
  );
}
