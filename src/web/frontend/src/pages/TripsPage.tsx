import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Trash2 } from 'lucide-react';
import { api, type Trip } from '@/api/client';
import { Button } from '@/components/ui/button';
import { PageCard } from '@/components/ui/cards';
import { TransactionRow } from '@/components/transactions/TransactionRow';
import { ActiveTripCard } from '@/components/trips/ActiveTripCard';

const TX_PAGE_SIZE = 20;

// ── TripRow ──────────────────────────────────────────────────────────────────

function TripRow({ trip }: { trip: Trip }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [txPage, setTxPage] = useState(1);
  const [delistingId, setDelistingId] = useState<number | null>(null);

  const { data: summary } = useQuery({
    queryKey: ['trip-summary', trip.id],
    queryFn: () => api.getTripSummary(trip.id),
    enabled: expanded,
    staleTime: 60_000,
  });

  const { data: txs = [] } = useQuery({
    queryKey: ['trip-transactions', trip.id],
    queryFn: () => api.getTripTransactions(trip.id, 1000),
    enabled: expanded,
    staleTime: 30_000,
  });

  const activateMutation = useMutation({
    mutationFn: () => api.activateTrip(trip.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trips'] });
      qc.invalidateQueries({ queryKey: ['trips-active'] });
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: () => api.deactivateTrip(trip.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trips'] });
      qc.invalidateQueries({ queryKey: ['trips-active'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteTrip(trip.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['trips'] }),
  });

  const delistMutation = useMutation({
    mutationFn: (txId: number) => api.delistTransaction(trip.id, txId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trip-transactions', trip.id] });
      qc.invalidateQueries({ queryKey: ['trip-summary', trip.id] });
      qc.invalidateQueries({ queryKey: ['trip-membership', trip.id] });
    },
  });

  const isActive = trip.status === 'active';
  const isPendingToggle = activateMutation.isPending || deactivateMutation.isPending;

  const handleToggle = () => {
    if (isPendingToggle) return;
    if (isActive) {
      deactivateMutation.mutate();
    } else {
      activateMutation.mutate();
    }
  };

  const handleCollapse = () => {
    setExpanded(false);
    setTxPage(1);
  };

  const totalTxPages = Math.ceil(txs.length / TX_PAGE_SIZE);
  const pageTxs = txs.slice((txPage - 1) * TX_PAGE_SIZE, txPage * TX_PAGE_SIZE);

  const dateLabel = trip.end_date
    ? `${trip.start_date} → ${trip.end_date}`
    : trip.start_date;

  return (
    <div className="py-3 border-b border-border last:border-b-0">
      {/* Row header */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={expanded ? handleCollapse : () => setExpanded(true)}
        >
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </Button>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-foreground leading-tight">{trip.name}</p>
          <p className="text-xs text-muted">
            {trip.destination ? `${trip.destination} · ` : ''}{dateLabel}
          </p>
        </div>

        {/* Auto-assign toggle */}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-xs text-muted hidden sm:inline">Auto-assign</span>
          <button
            onClick={handleToggle}
            disabled={isPendingToggle}
            className={`relative w-10 h-5 rounded-full transition-colors disabled:opacity-50 ${
              isActive ? 'bg-success' : 'bg-foreground/20'
            }`}
            title={isActive ? 'Active — click to deactivate' : 'Inactive — click to activate'}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                isActive ? 'translate-x-5' : 'translate-x-0'
              }`}
            />
          </button>
        </div>

        {/* Delete */}
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-destructive shrink-0"
          onClick={() => {
            if (confirm(`Delete trip "${trip.name}"?`)) deleteMutation.mutate();
          }}
          disabled={deleteMutation.isPending}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>

      {/* Expanded section */}
      {expanded && (
        <>
          {/* Stats + transaction list header — indented under chevron */}
          <div className="mt-3 ml-9 space-y-3">
            {summary && (
              <p className="text-xs text-muted">
                S${summary.total_sgd.toFixed(2)} · {summary.transaction_count} transactions ·
                S${summary.daily_average_sgd.toFixed(2)}/day
              </p>
            )}
            <div className="flex items-center justify-between">
              <p className="text-xs font-medium text-foreground">Transactions</p>
              {totalTxPages > 1 && (
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setTxPage((p) => Math.max(1, p - 1))}
                    disabled={txPage === 1}
                  >
                    <ChevronLeft className="h-3 w-3" />
                  </Button>
                  <span className="text-xs text-muted">{txPage}/{totalTxPages}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setTxPage((p) => Math.min(totalTxPages, p + 1))}
                    disabled={txPage === totalTxPages}
                  >
                    <ChevronRight className="h-3 w-3" />
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Transaction rows — full card width */}
          {txs.length === 0 ? (
            <p className="ml-9 mt-1 text-xs text-muted">Nothing captured this period.</p>
          ) : (
            <div className="mt-2 border-t border-border">
              {pageTxs.map((tx) => (
                <TransactionRow
                  key={tx.id}
                  tx={tx}
                  readOnly
                  onRemove={() => {
                    setDelistingId(tx.id);
                    delistMutation.mutate(tx.id, {
                      onSettled: () => setDelistingId(null),
                    });
                  }}
                  removeDisabled={delistingId === tx.id}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── TripsPage ────────────────────────────────────────────────────────────────

export function TripsPage() {
  const qc = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newStartDate, setNewStartDate] = useState(new Date().toISOString().split('T')[0]);
  const [newEndDate, setNewEndDate] = useState('');
  const [newDest, setNewDest] = useState('');

  const { data: trips = [], isLoading } = useQuery({
    queryKey: ['trips'],
    queryFn: () => api.getTrips(),
    staleTime: 30_000,
  });

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const trip = await api.createTrip({
        name: newName,
        start_date: newStartDate,
        destination: newDest || undefined,
      });
      if (newEndDate) {
        // best-effort — trip is already created; end_date is optional metadata
        await api.updateTrip(trip.id, { end_date: newEndDate }).catch(() => {});
      }
      return trip;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trips'] });
      setShowCreateForm(false);
      setNewName('');
      setNewDest('');
      setNewEndDate('');
    },
  });

  if (!settings?.trips_enabled) {
    return (
      <div className="p-6 flex flex-col items-center justify-center min-h-48 text-center gap-3">
        <p className="text-muted text-sm">Enable Trips in Settings to get started.</p>
        <a
          href="/settings"
          className="text-sm underline underline-offset-2 text-foreground/70 hover:text-foreground"
        >
          Go to Settings →
        </a>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4 pb-20 md:pb-0">
      <h1 className="text-lg font-semibold text-foreground">Trips</h1>

      {/* Active trip summary */}
      <ActiveTripCard showEndButton />

      {/* All trips */}
      <PageCard
        title="All Trips"
        action={
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => setShowCreateForm((v) => !v)}
          >
            {showCreateForm ? 'Cancel' : '+ New Trip'}
          </Button>
        }
      >
        {/* Create form (collapsible) */}
        {showCreateForm && (
          <div className="space-y-3 pb-4 border-b border-border mb-2">
            <div className="flex flex-wrap gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Trip name"
                className="input-field flex-1 min-w-40"
              />
              <label className="flex flex-col gap-1">
                <span className="text-xs text-muted">Start date</span>
                <input
                  type="date"
                  value={newStartDate}
                  onChange={(e) => setNewStartDate(e.target.value)}
                  className="input-field"
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                type="text"
                value={newDest}
                onChange={(e) => setNewDest(e.target.value)}
                placeholder="Destination (optional)"
                className="input-field flex-1 min-w-32"
              />
              <label className="flex flex-col gap-1">
                <span className="text-xs text-muted">End date (optional)</span>
                <input
                  type="date"
                  value={newEndDate}
                  onChange={(e) => setNewEndDate(e.target.value)}
                  className="input-field"
                />
              </label>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => createMutation.mutate()}
                disabled={!newName || !newStartDate || createMutation.isPending}
                className="btn-action disabled:opacity-40"
              >
                {createMutation.isPending ? 'Creating…' : 'Create Trip'}
              </button>
            </div>
          </div>
        )}

        {/* Trip list */}
        {isLoading ? (
          <div className="h-24 animate-pulse bg-foreground/10 rounded-md" />
        ) : trips.length === 0 ? (
          <p className="text-muted text-sm text-center py-8">
            No trips yet. Create one to start grouping transactions.
          </p>
        ) : (
          trips.map((trip) => <TripRow key={trip.id} trip={trip} />)
        )}
      </PageCard>
    </div>
  );
}
