import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { formatCurrency } from '@/lib/utils';

interface ComparisonData {
  category: string;
  current: number;
  previous: number;
}

export function ComparisonBarChart({ data }: { data: ComparisonData[] }) {
  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <XAxis
            dataKey="category"
            tick={{ fontSize: 11, fill: '#72727E' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: string) => v.replace(/\s*[\u{1F000}-\u{1FFFF}]/gu, '').trim()}
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
            formatter={(value) => value != null ? formatCurrency(Number(value)) : ''}
          />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
          <Bar dataKey="current" name="This period" fill="#00D4AA" radius={[4, 4, 0, 0]} />
          <Bar dataKey="previous" name="Last period" fill="#3A3A46" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
