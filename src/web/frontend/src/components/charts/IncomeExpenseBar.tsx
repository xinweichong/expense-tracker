import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { api } from '@/api/client';
import { Card } from '@/components/ui/card';

const COLOR_INCOME = '#22c55e';
const COLOR_EXPENSE = '#ef4444';

function formatMonth(month: string): string {
  // "2026-04" → "Apr"
  const [year, m] = month.split('-');
  return new Date(Number(year), Number(m) - 1, 1).toLocaleString('default', { month: 'short' });
}

export function IncomeExpenseBar() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['income-vs-expense'],
    queryFn: () => api.getIncomeVsExpense(6),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <Card className="p-4 bg-card border-border">
        <h3 className="text-sm font-medium mb-4">Income vs Expenses — Last 6 Months</h3>
        <div className="h-64 flex items-center justify-center text-muted text-sm">Loading…</div>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card className="p-4 bg-card border-border">
        <h3 className="text-sm font-medium mb-4">Income vs Expenses — Last 6 Months</h3>
        <div className="h-64 flex items-center justify-center text-muted text-sm">Failed to load data</div>
      </Card>
    );
  }

  if (!data || data.length === 0) return null;

  const chartData = data.map((d) => ({
    month: formatMonth(d.month),
    Income: d.income,
    Expenses: d.expenses,
  }));

  return (
    <Card className="p-4 bg-card border-border">
      <h3 className="text-sm font-medium mb-4">Income vs Expenses — Last 6 Months</h3>
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <XAxis
              dataKey="month"
              tick={{ fontSize: 11, fill: '#72727E' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#72727E' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `$${v}`}
            />
            <Tooltip
              cursor={{ fill: '#1C1C22' }}
              contentStyle={{
                background: '#16161A',
                border: '1px solid #2A2A32',
                borderRadius: '8px',
                fontSize: '13px',
              }}
              formatter={(value) => value != null
                ? `$${Number(value).toLocaleString('en-SG', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`
                : ''}
            />
            <Legend wrapperStyle={{ fontSize: '12px', color: '#72727E' }} />
            <Bar dataKey="Income" fill={COLOR_INCOME} radius={[4, 4, 0, 0]} />
            <Bar dataKey="Expenses" fill={COLOR_EXPENSE} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
