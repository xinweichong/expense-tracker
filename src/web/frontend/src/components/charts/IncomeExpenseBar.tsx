import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { api } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

const COLOR_INCOME = '#22c55e';
const COLOR_EXPENSE = '#ef4444';

function formatMonth(month: string): string {
  // "2026-04" → "Apr"
  const [year, m] = month.split('-');
  return new Date(Number(year), Number(m) - 1, 1).toLocaleString('default', { month: 'short' });
}

function formatSGD(value: number): string {
  return `$${value.toLocaleString('en-SG', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export function IncomeExpenseBar() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['income-vs-expense'],
    queryFn: () => api.getIncomeVsExpense(6),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader><CardTitle>Income vs Expenses</CardTitle></CardHeader>
        <CardContent><div className="h-48 flex items-center justify-center text-muted text-sm">Loading…</div></CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardHeader><CardTitle className="text-base">Income vs Expenses — Last 6 Months</CardTitle></CardHeader>
        <CardContent><div className="h-48 flex items-center justify-center text-muted text-sm">Failed to load data</div></CardContent>
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
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Income vs Expenses — Last 6 Months</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
            <XAxis dataKey="month" tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={40} />
            <Tooltip
              formatter={(value, name) => [formatSGD(Number(value)), String(name)]}
              contentStyle={{ background: '#16161A', border: '1px solid #2A2A32', borderRadius: 8 }}
              labelStyle={{ color: 'hsl(var(--foreground))', fontWeight: 600 }}
            />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            <Bar dataKey="Income" fill={COLOR_INCOME} radius={[3, 3, 0, 0]} />
            <Bar dataKey="Expenses" fill={COLOR_EXPENSE} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
