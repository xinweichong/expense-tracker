import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Ban, Pencil, Trash2 } from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { ChartCard } from '@/components/ui/cards';
import {
  CHART_AXIS_PROPS,
  CHART_CURSOR_BAR,
  CHART_TOOLTIP_STYLE,
  COLOR_TEAL,
} from '@/lib/chartTheme';
import { api, type Subscription, type Transaction, type UpcomingTransaction } from '@/api/client';
import { SubscriptionForm } from './SubscriptionForm';

interface SubscriptionSheetProps {
  subId: number;
  onClose: () => void;
  onMutate: () => void;
}

const FREQUENCY_LABELS: Record<Subscription['frequency'], string> = {
  weekly: 'Weekly',
  biweekly: 'Biweekly',
  monthly: 'Monthly',
  quarterly: 'Quarterly',
  annual: 'Annual',
};

const FREQUENCY_MONTHLY_FACTOR: Record<Subscription['frequency'], number> = {
  weekly: 4.33,
  biweekly: 2.17,
  monthly: 1,
  quarterly: 1 / 3,
  annual: 1 / 12,
};

export function SubscriptionSheet({ subId, onClose, onMutate }: SubscriptionSheetProps) {
  const qc = useQueryClient();
  const [showEdit, setShowEdit] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [adoptPrompt, setAdoptPrompt] = useState<{ txMerchant: string } | null>(null);

  const { data: list } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: () => api.getSubscriptions(),
  });
  const sub = list?.subscriptions.find((s) => s.id === subId);

  const { data: history = [] } = useQuery({
    queryKey: ['subscription-history', subId],
    queryFn: () => api.getSubscriptionHistory(subId, 50),
    enabled: sub != null,
  });

  const { data: upcoming = [] } = useQuery({
    queryKey: ['subscription-upcoming', subId],
    queryFn: () => api.getSubscriptionUpcoming(subId),
    enabled: sub != null,
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.updateSubscription(subId, { status: 'cancelled' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      onMutate();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteSubscription(subId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      onMutate();
    },
  });

  const dismissMutation = useMutation({
    mutationFn: (upcomingId: number) => api.dismissUpcoming(subId, upcomingId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscription-upcoming', subId] });
    },
  });

  const matchMutation = useMutation({
    mutationFn: ({ upcomingId, txId }: { upcomingId: number; txId: number }) =>
      api.matchUpcoming(subId, upcomingId, txId).then(() => txId),
    onSuccess: (txId) => {
      qc.invalidateQueries({ queryKey: ['subscription-upcoming', subId] });
      qc.invalidateQueries({ queryKey: ['subscription-history', subId] });
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      const matchedTx = recentTxs.find((t) => t.id === txId);
      if (matchedTx && sub && matchedTx.merchant && matchedTx.merchant !== sub.merchant) {
        setAdoptPrompt({ txMerchant: matchedTx.merchant });
      }
    },
  });

  const adoptMutation = useMutation({
    mutationFn: (merchant: string) => api.updateSubscription(subId, { merchant }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      setAdoptPrompt(null);
    },
  });

  // Pull recent transactions for manual match picker — last 90 days, no merchant filter.
  const today = new Date().toISOString().slice(0, 10);
  const ninetyDaysAgo = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const { data: recentTxs = [] } = useQuery({
    queryKey: ['transactions', 'match-picker', ninetyDaysAgo, today],
    queryFn: () =>
      api.getTransactions({
        start_date: ninetyDaysAgo,
        end_date: today,
        limit: 50,
      }) as Promise<Transaction[]>,
    enabled: sub != null,
  });

  const pendingUpcomings = upcoming.filter((u) => u.status === 'pending');

  const trendData = useMemo(() => {
    return history
      .slice(0, 6)
      .map((t) => ({
        date: t.transaction_date.slice(0, 10),
        amount: Number((t.amount * t.exchange_rate).toFixed(2)),
      }))
      .reverse();
  }, [history]);

  const monthlyCost = sub && sub.last_amount != null
    ? sub.last_amount * FREQUENCY_MONTHLY_FACTOR[sub.frequency]
    : null;

  return (
    <>
      <Sheet open onOpenChange={(open) => { if (!open) onClose(); }}>
        <SheetContent side="right" className="flex flex-col h-full p-0 w-full sm:max-w-lg">
          <SheetHeader className="shrink-0 px-4 py-3 border-b border-border">
            <div className="flex flex-col gap-1">
              <SheetTitle className="text-base">
                {sub?.label ?? sub?.merchant ?? 'Subscription'}
              </SheetTitle>
              {sub && (
                <div className="flex items-center gap-2 text-xs text-muted">
                  <span>{FREQUENCY_LABELS[sub.frequency]}</span>
                  {sub.status === 'possibly_cancelled' && (
                    <span className="text-warning">⚠ Possibly cancelled</span>
                  )}
                  {sub.status === 'cancelled' && <span>Cancelled</span>}
                </div>
              )}
            </div>
          </SheetHeader>

          {/* Action bar — persistent chrome */}
          {sub && (
            <div className="shrink-0 border-b border-border">
              {confirmCancel ? (
                <div className="flex items-center justify-between px-4 py-2 gap-3">
                  <span className="text-sm text-foreground">Cancel this subscription?</span>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => setConfirmCancel(false)}
                      className="px-3 py-1 text-xs text-muted hover:text-foreground"
                    >
                      Back
                    </button>
                    <button
                      onClick={() => { setConfirmCancel(false); cancelMutation.mutate(); }}
                      disabled={cancelMutation.isPending}
                      className="px-3 py-1 text-xs bg-warning text-background rounded-md disabled:opacity-40"
                    >
                      {cancelMutation.isPending ? 'Cancelling…' : 'Confirm'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex gap-2 px-4 py-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => setShowEdit(true)}
                    aria-label="Edit"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </Button>
                  {sub.status !== 'cancelled' && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-warning"
                      onClick={() => setConfirmCancel(true)}
                      aria-label="Cancel subscription"
                    >
                      <Ban className="w-3.5 h-3.5" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-destructive"
                    onClick={() => setConfirmDelete(true)}
                    aria-label="Delete"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Scrollable body */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
            {!sub && <p className="text-sm text-muted">Loading…</p>}

            {sub && (
              <>
                {/* Stats row */}
                <div className="grid grid-cols-3 gap-2">
                  <Stat label="Monthly" value={monthlyCost != null ? `S$${monthlyCost.toFixed(2)}` : '—'} />
                  <Stat label="Last charge" value={sub.last_amount != null ? `S$${sub.last_amount.toFixed(2)}` : '—'} />
                  <Stat label="Next charge" value={sub.next_expected_date ? sub.next_expected_date.slice(0, 10) : '—'} />
                </div>

                {adoptPrompt && (
                  <div className="flex items-center justify-between p-3 rounded-md bg-warning/10 border border-warning/30 text-xs">
                    <span className="text-foreground">
                      Transaction merchant is <strong>{adoptPrompt.txMerchant}</strong>. Update subscription for future auto-matching?
                    </span>
                    <div className="flex gap-2 ml-3 shrink-0">
                      <button
                        onClick={() => adoptMutation.mutate(adoptPrompt.txMerchant)}
                        className="text-foreground underline underline-offset-2"
                      >
                        Yes
                      </button>
                      <button onClick={() => setAdoptPrompt(null)} className="text-muted">
                        No
                      </button>
                    </div>
                  </div>
                )}

                {trendData.length >= 2 && (
                  <ChartCard title="Recent charges">
                    <div className="h-32 px-2 pb-2">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={trendData}>
                          <XAxis dataKey="date" {...CHART_AXIS_PROPS} />
                          <YAxis {...CHART_AXIS_PROPS} />
                          <Tooltip contentStyle={CHART_TOOLTIP_STYLE} cursor={CHART_CURSOR_BAR} />
                          <Bar dataKey="amount" fill={COLOR_TEAL} radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </ChartCard>
                )}

                {pendingUpcomings.length > 0 && (
                  <section>
                    <h3 className="text-xs uppercase tracking-[0.18em] text-muted font-mono font-semibold mb-2">
                      Upcoming
                    </h3>
                    <div className="divide-y divide-border">
                      {pendingUpcomings.map((u) => (
                        <UpcomingRow
                          key={u.id}
                          upcoming={u}
                          recentTxs={recentTxs}
                          onMatch={(txId) => matchMutation.mutate({ upcomingId: u.id, txId })}
                          onDismiss={() => dismissMutation.mutate(u.id)}
                        />
                      ))}
                    </div>
                  </section>
                )}

                <section>
                  <h3 className="text-xs uppercase tracking-[0.18em] text-muted font-mono font-semibold mb-2">
                    History
                  </h3>
                  {history.length === 0 ? (
                    <p className="text-sm text-muted py-2">No matched transactions yet.</p>
                  ) : (
                    <div className="divide-y divide-border">
                      {history.map((tx) => (
                        <div key={tx.id} className="flex items-center justify-between py-2">
                          <div className="flex flex-col gap-0.5 min-w-0">
                            <span className="text-sm text-foreground truncate">{tx.merchant ?? '—'}</span>
                            <span className="text-xs text-muted">{tx.transaction_date.slice(0, 10)}</span>
                          </div>
                          <span className="text-sm tabular-nums text-foreground shrink-0 ml-2">
                            S${(tx.amount * tx.exchange_rate).toFixed(2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                {confirmDelete && (
                  <div className="p-3 rounded-md border border-destructive/30 bg-destructive/10 space-y-2">
                    <p className="text-sm text-foreground">
                      Delete this subscription permanently? Matched transactions are not deleted.
                    </p>
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => setConfirmDelete(false)}
                        className="px-3 py-1.5 text-sm text-muted hover:text-foreground"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate()}
                        disabled={deleteMutation.isPending}
                        className="px-3 py-1.5 text-sm bg-destructive text-white rounded-md disabled:opacity-40"
                      >
                        {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </SheetContent>
      </Sheet>

      {showEdit && sub && (
        <SubscriptionForm
          initial={sub}
          onClose={() => setShowEdit(false)}
          onSave={() => {
            setShowEdit(false);
            qc.invalidateQueries({ queryKey: ['subscriptions'] });
          }}
        />
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.18em] text-muted font-mono">{label}</p>
      <p className="text-sm font-semibold text-foreground tabular-nums truncate">{value}</p>
    </div>
  );
}

interface UpcomingRowProps {
  upcoming: UpcomingTransaction;
  recentTxs: Transaction[];
  onMatch: (txId: number) => void;
  onDismiss: () => void;
}

function UpcomingRow({ upcoming, recentTxs, onMatch, onDismiss }: UpcomingRowProps) {
  const [selectedTxId, setSelectedTxId] = useState<string>('');
  const candidates = recentTxs.slice(0, 20);

  return (
    <div className="py-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm text-foreground">
            Expected {upcoming.expected_date.slice(0, 10)}
          </span>
          {upcoming.expected_amount != null && (
            <span className="text-xs text-muted">
              S${upcoming.expected_amount.toFixed(2)}
            </span>
          )}
        </div>
        <button
          onClick={onDismiss}
          className="text-xs text-muted hover:text-foreground underline underline-offset-2"
        >
          Dismiss
        </button>
      </div>
      <div className="flex gap-2">
        <select
          value={selectedTxId}
          onChange={(e) => setSelectedTxId(e.target.value)}
          className="select-field flex-1 min-w-0"
        >
          <option value="">Match to transaction…</option>
          {candidates.map((tx) => (
            <option key={tx.id} value={String(tx.id)}>
              {tx.transaction_date.slice(0, 10)} · S${(tx.amount * tx.exchange_rate).toFixed(2)} · {tx.merchant ?? '—'}
            </option>
          ))}
        </select>
        <button
          onClick={() => {
            if (selectedTxId) onMatch(Number(selectedTxId));
          }}
          disabled={!selectedTxId}
          className="btn-action disabled:opacity-40"
        >
          Match
        </button>
      </div>
    </div>
  );
}
