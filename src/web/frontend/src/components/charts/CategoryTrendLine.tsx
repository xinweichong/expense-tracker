import { useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { formatCurrency, getCategoryColor } from '@/lib/utils';

export function CategoryTrendLine({ data }: { data: Record<string, any>[] }) {
  const categories = useMemo(() => {
    const cats = new Set<string>();
    data.forEach(d => Object.keys(d).filter(k => k !== 'date').forEach(k => cats.add(k)));
    return Array.from(cats).sort();
  }, [data]);

  if (!data || data.length === 0) {
    return <div className="h-56 flex items-center justify-center text-muted text-sm">No trend data</div>;
  }

  return (
    <div className="w-full h-56">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#72727E' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: string) => new Date(v).getDate().toString()}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#72727E' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `$${v}`}
          />
          <Tooltip
            cursor={{ stroke: '#2A2A32', strokeWidth: 1 }}
            contentStyle={{
              background: '#16161A',
              border: '1px solid #2A2A32',
              borderRadius: '8px',
              fontSize: '13px',
            }}
            formatter={(value: any, name: any) => [formatCurrency(Number(value ?? 0)), String(name ?? '')]}
            labelFormatter={(label) =>
              new Date(String(label)).toLocaleDateString('en-SG', { day: 'numeric', month: 'short' })
            }
          />
          <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
          {categories.map((cat) => (
            <Line
              key={cat}
              type="monotone"
              dataKey={cat}
              stroke={getCategoryColor(cat)}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
