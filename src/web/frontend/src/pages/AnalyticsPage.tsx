import { Card } from '@/components/ui/card';
import { BarChart3, TrendingUp, Store, Bell } from 'lucide-react';

const sections = [
  { icon: TrendingUp, title: 'Trend Comparisons', desc: 'Month-over-month spending analysis' },
  { icon: Store, title: 'Merchant Analysis', desc: 'Top merchants and spending patterns' },
  { icon: Bell, title: 'Smart Alerts', desc: 'Spending velocity and anomaly detection' },
  { icon: BarChart3, title: 'Summary Reports', desc: 'Weekly and monthly auto-generated summaries' },
];

export function AnalyticsPage() {
  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto space-y-4">
      <h1 className="text-xl font-bold">Analytics</h1>
      <p className="text-sm text-muted">Advanced analytics are coming in the next release.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {sections.map(({ icon: Icon, title, desc }) => (
          <Card key={title} className="p-4 bg-card border-border">
            <Icon className="w-8 h-8 text-muted mb-2" />
            <h3 className="text-sm font-medium">{title}</h3>
            <p className="text-xs text-muted mt-0.5">{desc}</p>
            <p className="text-xs text-accent mt-2">Coming soon</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
