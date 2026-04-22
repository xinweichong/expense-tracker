import { useId } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { formatCurrency } from '@/lib/utils';

interface TrendPoint {
  date: string;
  amount: number;
}

export function TrendLine({ data }: { data: TrendPoint[] }) {
  const gradientId = useId().replace(/:/g, '');

  if (!data || data.length === 0) {
    return <div className="h-48 flex items-center justify-center text-muted text-sm">No trend data</div>;
  }

  return (
    <div className="w-full h-48">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#00D4AA" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#00D4AA" stopOpacity={0} />
            </linearGradient>
          </defs>
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
            contentStyle={{
              background: '#16161A',
              border: '1px solid #2A2A32',
              borderRadius: '8px',
              fontSize: '13px',
            }}
            formatter={(value) => formatCurrency(Number(value ?? 0))}
            labelFormatter={(label) =>
              new Date(String(label)).toLocaleDateString('en-SG', { day: 'numeric', month: 'short' })
            }
          />
          <Area
            type="monotone"
            dataKey="amount"
            stroke="#00D4AA"
            strokeWidth={2}
            fill={`url(#${gradientId})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
