import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { api } from '@/api/client';
import { Badge } from '@/components/ui/badge';
import { ChartCard } from '@/components/ui/cards';
import { CHART_AXIS_PROPS, CHART_TOOLTIP_STYLE, CHART_CURSOR_BAR, COLOR_ACCENT } from '@/lib/chartTheme';
import { X } from 'lucide-react';

const TAG_COLORS: Record<string, string> = {
  online:           'bg-blue-500/20 text-blue-400 border-blue-500/30',
  subscription:     'bg-purple-500/20 text-purple-400 border-purple-500/30',
  local:            'bg-green-500/20 text-green-400 border-green-500/30',
  foreign:          'bg-orange-500/20 text-orange-400 border-orange-500/30',
  business:         'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  'cash-equivalent':'bg-zinc-500/20 text-zinc-400 border-zinc-500/30',
};

const ALL_TAGS = Object.keys(TAG_COLORS);

function formatSGD(v: number) {
  return `$${v.toLocaleString('en-SG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function MerchantProfile({
  merchant,
  onClose,
}: {
  merchant: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();

  const { data: profile, isLoading } = useQuery({
    queryKey: ['merchant-profile', merchant],
    queryFn: () => api.getMerchantProfile(merchant),
    enabled: !!merchant,
  });

  const { data: trend } = useQuery({
    queryKey: ['merchant-trend', merchant],
    queryFn: () => api.getMerchantTrend(merchant),
    enabled: !!merchant,
  });

  const setTagsMutation = useMutation({
    mutationFn: (tags: string[]) => api.setMerchantTags(merchant, tags),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['merchant-profile', merchant] });
      qc.invalidateQueries({ queryKey: ['merchant-intelligence'] });
    },
  });

  const [notes, setNotes] = useState('');
  const [notesSaved, setNotesSaved] = useState(false);
  const setNotesMutation = useMutation({
    mutationFn: (n: string) => api.setMerchantNotes(merchant, n),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['merchant-profile', merchant] });
      setNotesSaved(true);
      setTimeout(() => setNotesSaved(false), 1500);
    },
  });

  useEffect(() => {
    setNotes(profile?.notes ?? '');
  }, [merchant]); // reset notes when merchant changes

  const toggleTag = (tag: string) => {
    if (!profile) return;
    const current = profile.tags ?? [];
    const next = current.includes(tag)
      ? current.filter((t) => t !== tag)
      : [...current, tag];
    setTagsMutation.mutate(next);
  };

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        Loading…
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="h-full flex items-center justify-center text-muted text-sm">
        Merchant not found.
      </div>
    );
  }

  const chartData = (trend?.months ?? []).map((m) => ({
    month: m.month.slice(5),   // "2026-04" → "04"
    Total: m.total,
  }));

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-bold text-foreground">{profile.merchant}</h2>
          {profile.category && (
            <Badge variant="outline" className="mt-1 text-xs">{profile.category}</Badge>
          )}
        </div>
        <button onClick={onClose} className="text-muted hover:text-foreground p-1">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-2">
        {[
          { label: 'Total Spent', value: formatSGD(profile.total_sgd) },
          { label: 'Transactions', value: String(profile.transaction_count) },
          { label: 'Average', value: formatSGD(profile.avg_amount_sgd) },
          { label: 'Last Seen', value: profile.last_seen ?? '—' },
        ].map(({ label, value }) => (
          <div key={label} className="bg-background rounded-lg p-3 border border-border">
            <p className="text-xs text-muted">{label}</p>
            <p className="text-sm font-semibold text-foreground mt-0.5">{value}</p>
          </div>
        ))}
      </div>

      {/* Spend trend — ChartCard used here (Recharts does not support CSS custom properties; all values come from chartTheme.ts) */}
      {chartData.length > 0 && (
        <ChartCard title="Monthly Spend">
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
              <XAxis dataKey="month" {...CHART_AXIS_PROPS} />
              <YAxis hide />
              <Tooltip
                formatter={(v) => [formatSGD(Number(v ?? 0)), 'Spent']}
                contentStyle={CHART_TOOLTIP_STYLE}
                cursor={CHART_CURSOR_BAR}
              />
              <Bar dataKey="Total" fill={COLOR_ACCENT} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      )}

      {/* Tags */}
      <div>
        <p className="text-xs font-medium text-muted mb-2">TAGS</p>
        <div className="flex flex-wrap gap-2">
          {ALL_TAGS.map((tag) => {
            const active = (profile.tags ?? []).includes(tag);
            return (
              <button
                key={tag}
                onClick={() => toggleTag(tag)}
                className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                  active
                    ? TAG_COLORS[tag]
                    : 'border-border text-muted hover:text-foreground'
                }`}
              >
                {tag}
              </button>
            );
          })}
        </div>
      </div>

      {/* Notes */}
      <div>
        <p className="text-xs font-medium text-muted mb-2">NOTES</p>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => setNotesMutation.mutate(notes)}
          placeholder="Add notes about this merchant…"
          className="w-full h-20 px-3 py-2 text-sm bg-background border border-border rounded-md text-foreground placeholder:text-muted resize-none focus:outline-none focus:ring-1 focus:ring-border"
        />
        {notesSaved && (
          <p className="text-xs text-success mt-1">Saved</p>
        )}
      </div>
    </div>
  );
}
