import { Card } from '@/components/ui/card';
import { ComparisonBarChart } from '@/components/charts/ComparisonBarChart';
import { MerchantTable } from '@/components/charts/MerchantTable';
import { VelocityRing } from '@/components/charts/VelocityRing';
import { api } from '@/api/client';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '@/lib/utils';
import { AlertTriangle, TrendingUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

export function AnalyticsPage() {
  const { data: comparison } = useQuery({
    queryKey: ['analytics-comparison'],
    queryFn: () => api.getAnalyticsComparison('month'),
  });

  const { data: merchants } = useQuery({
    queryKey: ['analytics-merchants'],
    queryFn: () => api.getAnalyticsMerchants(10),
  });

  const { data: velocity } = useQuery({
    queryKey: ['analytics-velocity'],
    queryFn: () => api.getAnalyticsVelocity(),
  });

  const { data: alerts } = useQuery({
    queryKey: ['analytics-alerts'],
    queryFn: () => api.getAnalyticsAlerts(),
  });

  const hasAlerts = (alerts?.anomalies?.length ?? 0) > 0 || (alerts?.new_merchants?.length ?? 0) > 0;

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-5xl mx-auto space-y-4 md:space-y-6">
      <h1 className="text-xl font-bold">Analytics</h1>

      {/* Alerts */}
      {hasAlerts && (
        <Card className="p-4 bg-card border-accent/30">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-accent shrink-0 mt-0.5" />
            <div className="space-y-1">
              {alerts.anomalies?.map((a: any) => (
                <p key={a.id} className="text-sm">
                  Unusual: <span className="font-medium">{a.merchant}</span>{' '}
                  {formatCurrency(a.amount)} in {a.category}
                </p>
              ))}
              {alerts.new_merchants?.slice(0, 3).map((m: any) => (
                <p key={m.merchant} className="text-sm">
                  New merchant: <span className="font-medium">{m.merchant}</span>
                </p>
              ))}
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Period Comparison */}
        <Card className="p-4 bg-card border-border">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium">Period Comparison</h3>
            {comparison?.overall && (
              <Badge variant="outline" className="border-border text-xs">
                <TrendingUp className="w-3 h-3 mr-1" />
                {comparison.overall.change_percent != null
                  ? `${comparison.overall.change_percent > 0 ? '+' : ''}${comparison.overall.change_percent}%`
                  : 'New'}
              </Badge>
            )}
          </div>
          {comparison?.categories && (
            <ComparisonBarChart data={comparison.categories} />
          )}
        </Card>

        {/* Spending Velocity */}
        <Card className="p-4 bg-card border-border">
          <h3 className="text-sm font-medium mb-4">Spending Velocity</h3>
          {velocity && <VelocityRing data={velocity} />}
        </Card>
      </div>

      {/* Top Merchants */}
      <Card className="p-4 bg-card border-border">
        <h3 className="text-sm font-medium mb-4">Top Merchants This Month</h3>
        <MerchantTable data={merchants?.top ?? []} />
      </Card>
    </div>
  );
}
