import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type Trip } from '@/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TransactionRow } from '@/components/transactions/TransactionRow';

// ── Active Trip Banner ───────────────────────────────────────────────────────

function ActiveTripBanner({ trip }: { trip: Trip }) {
  const qc = useQueryClient();
  const { data: summary } = useQuery({
    queryKey: ['trip-summary', trip.id],
    queryFn: () => api.getTripSummary(trip.id),
    staleTime: 30_000,
  });
  const { data: txs = [] } = useQuery({
    queryKey: ['trip-transactions', trip.id],
    queryFn: () => api.getTripTransactions(trip.id),
    staleTime: 30_000,
  });

  const deactivateMutation = useMutation({
    mutationFn: () => api.deactivateTrip(trip.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trips'] });
      qc.invalidateQueries({ queryKey: ['trips-active'] });
    },
  });

  const delistMutation = useMutation({
    mutationFn: (txId: number) => api.delistTransaction(trip.id, txId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trip-transactions', trip.id] });
      qc.invalidateQueries({ queryKey: ['trip-summary', trip.id] });
    },
  });

  const start = new Date(trip.start_date);
  const daysElapsed = Math.max(1, Math.floor((Date.now() - start.getTime()) / 86400000) + 1);

  return (
    <div className="space-y-4">
      {/* Active trip header */}
      <Card className="border-accent/40 bg-accent/5">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-semibold text-foreground">✈️ {trip.name}</span>
                <span className="text-xs px-1.5 py-0.5 rounded bg-accent/20 text-accent font-medium">Active</span>
              </div>
              {trip.destination && (
                <p className="text-xs text-muted mt-0.5">{trip.destination}</p>
              )}
              <p className="text-xs text-muted mt-0.5">
                Day {daysElapsed} · started {trip.start_date}
              </p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-xl font-bold text-foreground">S${summary?.total_sgd.toFixed(2) ?? '—'}</p>
              <p className="text-xs text-muted">
                {summary?.transaction_count ?? 0} transactions · S${summary?.daily_average_sgd.toFixed(2) ?? '—'}/day
              </p>
              <button
                onClick={() => {
                  if (confirm('End this trip?')) deactivateMutation.mutate();
                }}
                className="mt-2 text-xs px-2.5 py-1 border border-border rounded-md text-muted hover:text-foreground transition-colors"
              >
                End Trip
              </button>
            </div>
          </div>

          {/* By-category summary */}
          {summary && summary.by_category.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
              {summary.by_category.map((c) => (
                <span key={c.category} className="text-xs text-muted">
                  {c.category}: <span className="text-foreground">S${c.amount_sgd.toFixed(0)}</span>
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Transaction list */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Transactions</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {txs.length === 0 ? (
            <p className="text-muted text-sm py-6 text-center">No transactions yet.</p>
          ) : (
            txs.map((tx) => (
              <div key={tx.id} className="flex items-center">
                <div className="flex-1 min-w-0">
                  <TransactionRow tx={tx} />
                </div>
                <button
                  onClick={() => delistMutation.mutate(tx.id)}
                  className="shrink-0 px-3 py-2 text-xs text-destructive hover:opacity-75 transition-colors"
                  title="Remove from trip"
                >
                  ×
                </button>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ── Trip List (inactive view) ────────────────────────────────────────────────

function TripCard({ trip }: { trip: Trip }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const { data: summary } = useQuery({
    queryKey: ['trip-summary', trip.id],
    queryFn: () => api.getTripSummary(trip.id),
    enabled: expanded,
    staleTime: 60_000,
  });

  const activateMutation = useMutation({
    mutationFn: () => api.activateTrip(trip.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['trips'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteTrip(trip.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['trips'] }),
  });

  return (
    <div className="py-4 border-b border-border last:border-b-0">
      <div className="flex items-start justify-between gap-4">
        <button onClick={() => setExpanded(!expanded)} className="flex-1 min-w-0 text-left">
          <p className="text-sm font-semibold text-foreground">{trip.name}</p>
          <p className="text-xs text-muted">
            {trip.destination ? `${trip.destination} · ` : ''}{trip.start_date}
          </p>
        </button>
        <div className="flex items-center gap-2 shrink-0">
          {/* Active toggle */}
          <button
            onClick={() => {
              if (trip.status === 'inactive') {
                activateMutation.mutate();
              }
            }}
            className={`relative w-10 h-5 rounded-full transition-colors ${
              trip.status === 'active' ? 'bg-success' : 'bg-foreground/20'
            }`}
            title={trip.status === 'active' ? 'Active' : 'Activate'}
          >
            <span
              className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                trip.status === 'active' ? 'translate-x-5' : 'translate-x-0.5'
              }`}
            />
          </button>
          <button
            onClick={() => {
              if (confirm(`Delete trip "${trip.name}"?`)) deleteMutation.mutate();
            }}
            className="text-xs text-destructive hover:opacity-75 transition-colors px-1"
          >
            ✕
          </button>
        </div>
      </div>

      {/* Expanded summary */}
      {expanded && summary && (
        <div className="mt-3 pl-2 space-y-1 border-l-2 border-border">
          <p className="text-xs text-muted">
            S${summary.total_sgd.toFixed(2)} · {summary.transaction_count} transactions · {summary.days} days
          </p>
          {summary.by_category.slice(0, 3).map((c) => (
            <p key={c.category} className="text-xs text-muted">
              {c.category}: S${c.amount_sgd.toFixed(2)}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main TripsPage ────────────────────────────────────────────────────────────

export function TripsPage() {
  const qc = useQueryClient();
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDate, setNewDate] = useState(new Date().toISOString().split('T')[0]);
  const [newDest, setNewDest] = useState('');
  const [newCurrency, setNewCurrency] = useState('SGD');

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
    mutationFn: () =>
      api.createTrip({
        name: newName,
        start_date: newDate,
        destination: newDest || undefined,
        primary_currency: newCurrency,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trips'] });
      setShowCreateForm(false);
      setNewName('');
      setNewDest('');
    },
  });

  const activeTrip = trips.find((t) => t.status === 'active') ?? null;

  if (!settings?.trips_enabled) {
    return (
      <div className="p-6 flex flex-col items-center justify-center min-h-48 text-center gap-3">
        <p className="text-muted text-sm">Enable Trips in Settings to get started.</p>
        <a href="/settings" className="text-sm underline underline-offset-2 text-foreground/70 hover:text-foreground">
          Go to Settings →
        </a>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4 pb-20 md:pb-0">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-foreground">Trips</h1>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="text-xs px-2.5 py-1 border border-border rounded-md text-muted hover:text-foreground transition-colors"
        >
          {showCreateForm ? 'Cancel' : '+ New Trip'}
        </button>
      </div>

      {/* Create trip form */}
      {showCreateForm && (
        <Card>
          <CardContent className="p-4 space-y-3">
            <p className="text-sm font-medium text-foreground">Create Trip</p>
            <div className="flex flex-wrap gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Trip name"
                className="input-field flex-1 min-w-40"
              />
              <input
                type="date"
                value={newDate}
                onChange={(e) => setNewDate(e.target.value)}
                className="input-field"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <input
                type="text"
                value={newDest}
                onChange={(e) => setNewDest(e.target.value)}
                placeholder="Destination (optional)"
                className="input-field flex-1 min-w-32"
              />
              <input
                type="text"
                value={newCurrency}
                onChange={(e) => setNewCurrency(e.target.value.toUpperCase())}
                placeholder="Currency"
                maxLength={3}
                className="input-field w-24"
              />
            </div>
            <button
              onClick={() => createMutation.mutate()}
              disabled={!newName || !newDate || createMutation.isPending}
              className="px-3 py-1.5 text-sm bg-foreground text-background rounded-md hover:opacity-90 disabled:opacity-40"
            >
              Create Trip
            </button>
          </CardContent>
        </Card>
      )}

      {/* Active trip */}
      {activeTrip && <ActiveTripBanner trip={activeTrip} />}

      {/* All trips list */}
      {isLoading ? (
        <div className="h-24 animate-pulse bg-foreground/10 rounded-md" />
      ) : trips.length === 0 ? (
        <p className="text-muted text-sm text-center py-8">
          No trips yet. Create one to start grouping transactions.
        </p>
      ) : (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">All Trips</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-2">
            {trips.map((trip) => (
              <TripCard key={trip.id} trip={trip} />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
