import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { getCategoryColor, formatCurrency } from '@/lib/utils';

interface CategoryData {
  category: string;
  total: number;
}

export function CategoryDonut({ data }: { data: CategoryData[] }) {
  const total = data.reduce((sum, d) => sum + d.total, 0);

  return (
    <div>
      <div className="w-full aspect-square max-w-[220px] mx-auto">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="total"
              nameKey="category"
              cx="50%"
              cy="50%"
              innerRadius="60%"
              outerRadius="85%"
              paddingAngle={2}
              strokeWidth={0}
            >
              {data.map((entry, i) => (
                <Cell key={i} fill={getCategoryColor(entry.category)} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: '#16161A',
                border: '1px solid #2A2A32',
                borderRadius: '8px',
                fontSize: '13px',
              }}
              formatter={(value) => formatCurrency(Number(value ?? 0))}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="text-center -mt-6 relative z-10">
        <p className="text-xl font-bold">{formatCurrency(total)}</p>
        <p className="text-xs text-muted">Total spent</p>
      </div>
    </div>
  );
}
