import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { PageCard, ChartCard } from '@/components/ui/cards';
import { ComparisonBarChart } from '@/components/charts/ComparisonBarChart';
import { IncomeExpenseBar } from '@/components/charts/IncomeExpenseBar';
import { MerchantTable } from '@/components/charts/MerchantTable';
import { VelocityRing } from '@/components/charts/VelocityRing';
import { api } from '@/api/client';
import { useQuery } from '@tanstack/react-query';
import { formatCurrency } from '@/lib/utils';
import { AlertTriangle, TrendingUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const PILLAR_ORDER = [
  'savings_rate',
  'needs_ratio',
  'wants_ratio',
  'budget_adherence',
  'anomaly_frequency',
] as const;

function HealthScoreBreakdown() {
  const [months, setMonths] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ['health-score', months],
    queryFn: () => api.getHealthScore(months),
    staleTime: 60_000,
  });

  const score = data?.score ?? null;
  const ringColor =
    !score ? '#2A2A32' :
    score >= 80 ? '#30D158' :
    score >= 60 ? '#64D2FF' :
    score >= 40 ? '#FFD60A' :
    '#FF453A';

  const r = 40;
  const circ = 2 * Math.PI * r;
  const filled = score != null ? (score / 100) * circ : 0;

  const monthSelect = (
    <select
      value={months}
      onChange={(e) => setMonths(Number(e.target.value))}
      className="select-field text-xs"
    >
      <option value={1}>This month</option>
      <option value={3}>Last 3 months</option>
      <option value={6}>Last 6 months</option>
    </select>
  );

  return (
    <PageCard title="Financial Health Score" action={monthSelect}>
      {isLoading ? (
        <div className="h-48 animate-pulse bg-foreground/10 rounded-md" />
      ) : !data?.has_income_data ? (
        <div className="py-8 text-center">
          <p className="text-muted text-sm">No income transactions found for this period.</p>
          <p className="text-muted/60 text-xs mt-1">Add income transactions to calculate your health score.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Score header */}
          <div className="flex items-center gap-6">
            <svg width="96" height="96" className="shrink-0">
              <circle cx="48" cy="48" r={r} fill="none" stroke="#2A2A32" strokeWidth="6" />
              <circle
                cx="48" cy="48" r={r} fill="none"
                stroke={ringColor}
                strokeWidth="6"
                strokeDasharray={`${filled} ${circ}`}
                strokeLinecap="round"
                transform="rotate(-90 48 48)"
              />
              <text x="48" y="52" textAnchor="middle" fontSize="20" fontWeight="700" fill="#E8E8ED">
                {score}
              </text>
            </svg>
            <div>
              <p className="text-2xl font-bold text-foreground">{data.grade}</p>
              <p className="text-sm text-muted mt-1">Score for {data.period}</p>
              <p className="text-xs text-muted/70 mt-0.5">Based on the 50/30/20 rule</p>
            </div>
          </div>

          {/* Pillar breakdown */}
          <div className="space-y-4">
            {PILLAR_ORDER.map((key) => {
              const comp = data.components[key];
              if (!comp) return null;
              const pct = comp.score / comp.max;
              const barColor =
                pct >= 0.8  ? '#30D158' :
                pct >= 0.5  ? '#64D2FF' :
                pct >= 0.25 ? '#FFD60A' :
                '#FF453A';

              // Format the value label
              let valueLabel = '';
              if (key === 'anomaly_frequency') {
                valueLabel = `${comp.value} anomalies`;
              } else if (key === 'budget_adherence') {
                valueLabel = `${Math.round(comp.value * 100)}% within limit`;
              } else {
                const benchmarkStr = comp.benchmark != null ? ` / target ${Math.round(comp.benchmark * 100)}%` : '';
                valueLabel = `${Math.round((comp.value as number) * 100)}%${benchmarkStr}`;
              }

              return (
                <div key={key} className="space-y-1.5">
                  <div className="flex items-baseline justify-between">
                    <div>
                      <span className="text-sm font-medium text-foreground">{comp.label}</span>
                      <span className="text-xs text-muted ml-2">{valueLabel}</span>
                    </div>
                    <span className="text-sm font-semibold tabular-nums" style={{ color: barColor }}>
                      {comp.score}/{comp.max}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-foreground/10 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${pct * 100}%`, backgroundColor: barColor }}
                    />
                  </div>
                  <p className="text-xs text-muted/70">{comp.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </PageCard>
  );
}

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

  const comparisonBadge = comparison?.overall && (
    <Badge variant="outline" className="border-border text-xs">
      <TrendingUp className="w-3 h-3 mr-1" />
      {comparison.overall.change_percent != null
        ? `${comparison.overall.change_percent > 0 ? '+' : ''}${comparison.overall.change_percent}%`
        : 'New'}
    </Badge>
  );

  return (
    <div className="p-4 space-y-4 md:h-full md:overflow-hidden md:grid md:gap-4 md:p-6 md:space-y-0 page-grid-analytics">

      {/* ── Header area ── */}
      <div className="area-header">
        <h1 className="text-xl font-bold">Analytics</h1>
      </div>

      {/* ── Left panel: health score + alerts ── */}
      <div className="area-left grid-scroll-panel space-y-4">
        <HealthScoreBreakdown />

        {hasAlerts && (
          <Card className="p-4 border-warning/30">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="text-xs text-muted mb-2">
                  Unusual = transaction is over 2× the category average (last 30 days, min 3 transactions).
                  New merchant = first appearance this month.
                </p>
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
      </div>

      {/* ── Right panel: charts + merchants + income bar ── */}
      <div className="area-right grid-scroll-panel space-y-4">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ChartCard title="Period Comparison" action={comparisonBadge}>
            <div className="p-4">
              {comparison?.categories && (
                <ComparisonBarChart data={comparison.categories} />
              )}
            </div>
          </ChartCard>

          <PageCard title="Spending Velocity">
            {velocity && <VelocityRing data={velocity} />}
          </PageCard>
        </div>

        <PageCard title="Top Merchants This Month">
          <MerchantTable data={merchants?.top ?? []} />
        </PageCard>

        <IncomeExpenseBar />
      </div>

    </div>
  );
}
