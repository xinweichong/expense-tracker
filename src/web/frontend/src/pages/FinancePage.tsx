import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api, type BudgetProgress, type Category, type GoalProgress } from '@/api/client';
import { PageCard } from '@/components/ui/cards';
import { cn } from '@/lib/utils';
import { Pencil, Trash2 } from 'lucide-react';

function ProgressBar({ percent, status }: { percent: number; status: string }) {
  const color =
    status === 'over_budget' ? 'bg-destructive' :
    status === 'warning'     ? 'bg-warning' :
                               'bg-success';
  return (
    <div className="w-full h-2 bg-foreground/10 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all ${color}`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  );
}

function BudgetRow({
  b,
  onDelete,
  onEdit,
}: {
  b: BudgetProgress;
  onDelete: (id: number) => void;
  onEdit: (id: number, amount: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState(String(b.budget_amount));

  const handleSave = () => {
    const v = parseFloat(inputVal);
    if (!isNaN(v) && v > 0) {
      onEdit(b.id, v);
    }
    setEditing(false);
  };

  return (
    <div className="py-3 space-y-1.5 border-b border-border last:border-b-0">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-medium text-foreground">{b.label}</span>
          <span className="ml-2 text-xs text-muted capitalize">{b.period}</span>
        </div>
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <input
                type="number"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                className={cn('input-field', 'w-24 !py-1 !text-xs')}
              />
              <button onClick={handleSave} className="text-xs text-accent hover:text-accent/80">Save</button>
              <button onClick={() => setEditing(false)} className="text-xs text-muted hover:text-foreground">Cancel</button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)} className="text-xs text-muted hover:text-foreground">Edit</button>
              <button onClick={() => onDelete(b.id)} className="text-xs text-destructive hover:text-destructive/80">Delete</button>
            </>
          )}
        </div>
      </div>
      <ProgressBar percent={b.percent} status={b.status} />
      <div className="flex justify-between text-xs text-muted">
        <span>${b.spent.toFixed(2)} spent of ${b.budget_amount.toFixed(2)}</span>
        <span>
          {b.status === 'over_budget'
            ? `$${(b.spent - b.budget_amount).toFixed(2)} over`
            : `$${b.remaining.toFixed(2)} left · proj $${b.projected.toFixed(2)}`}
        </span>
      </div>
    </div>
  );
}

function AddBudgetForm({ categories, onAdd }: { categories: Category[]; onAdd: () => void }) {
  const qc = useQueryClient();
  const [category, setCategory] = useState<string>('__overall__');
  const [amount, setAmount] = useState('');
  const [period, setPeriod] = useState('monthly');
  const [error, setError] = useState('');

  const createMutation = useMutation({
    mutationFn: () =>
      api.createBudget({
        category: category === '__overall__' ? null : category,
        amount: parseFloat(amount),
        period,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['budget-progress'] });
      setAmount('');
      setCategory('__overall__');
      setPeriod('monthly');
      setError('');
      onAdd();
    },
    onError: (e: Error) => setError(e.message),
  });

  return (
    <div className="pt-4 border-t border-border space-y-3">
      <p className="text-sm font-medium text-foreground">Add Budget</p>
      <div className="flex flex-wrap gap-2">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className={cn('select-field', 'flex-1 min-w-32')}
        >
          <option value="__overall__">Overall</option>
          {categories.map((c) => (
            <option key={c.name} value={c.name}>{c.name}</option>
          ))}
        </select>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="select-field"
        >
          <option value="monthly">Monthly</option>
          <option value="weekly">Weekly</option>
        </select>
        <input
          type="number"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          placeholder="Amount"
          className={cn('input-field', 'w-28 placeholder:text-muted')}
        />
        <button
          onClick={() => createMutation.mutate()}
          disabled={!amount || parseFloat(amount) <= 0 || createMutation.isPending}
          className={cn('btn-action', 'disabled:opacity-40 transition-opacity')}
        >
          Add
        </button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

function ProgressRing({ percent }: { percent: number }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const filled = (Math.min(percent, 100) / 100) * circ;
  return (
    <svg width="88" height="88" className="shrink-0">
      <circle cx="44" cy="44" r={r} fill="none" stroke="var(--color-border)" strokeWidth="6" />
      <circle
        cx="44" cy="44" r={r} fill="none"
        stroke={percent >= 100 ? 'var(--color-success)' : 'var(--color-primary)'}
        strokeWidth="6"
        strokeDasharray={`${filled} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-90 44 44)"
      />
      <text x="44" y="48" textAnchor="middle" fontSize="14" fontWeight="600" fill="var(--color-foreground)">
        {percent.toFixed(0)}%
      </text>
    </svg>
  );
}

function GoalCard({ g, onContribute, onEdit, onDelete }: {
  g: GoalProgress;
  onContribute: (id: number, amount: number, note?: string) => void;
  onEdit: (id: number, data: { name?: string; target_amount?: number; target_date?: string }) => void;
  onDelete: (id: number) => void;
}) {
  const [contributing, setContributing] = useState(false);
  const [contribAmount, setContribAmount] = useState('');
  const [contribNote, setContribNote] = useState('');
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState('');
  const [editTarget, setEditTarget] = useState('');
  const [editDate, setEditDate] = useState('');

  const startEdit = () => {
    setEditName(g.name);
    setEditTarget(String(g.target_amount));
    setEditDate(g.target_date ?? '');
    setEditing(true);
    setContributing(false);
  };

  const handleEdit = () => {
    const t = parseFloat(editTarget);
    if (!editName.trim() || isNaN(t)) return;
    onEdit(g.id, { name: editName, target_amount: t, target_date: editDate || undefined });
    setEditing(false);
  };

  const handleContrib = () => {
    const v = parseFloat(contribAmount);
    if (!isNaN(v) && v > 0) {
      onContribute(g.id, v, contribNote || undefined);
      setContributing(false);
      setContribAmount('');
      setContribNote('');
    }
  };

  const onTrackColor =
    g.on_track === 'ahead'    ? 'text-success' :
    g.on_track === 'behind'   ? 'text-destructive' :
    g.on_track === 'on_track' ? 'text-info' : '';

  const onTrackLabel =
    g.on_track === 'ahead'    ? 'Ahead 🟢' :
    g.on_track === 'behind'   ? 'Behind 🔴' :
    g.on_track === 'on_track' ? 'On Track ✓' : null;

  if (editing) {
    return (
      <div className="py-4 border-b border-border last:border-b-0 space-y-2">
        <p className="text-xs text-muted font-medium">Edit Goal</p>
        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            placeholder="Goal name"
            className="input-field flex-1 min-w-36"
            autoFocus
          />
          <input
            type="number"
            value={editTarget}
            onChange={(e) => setEditTarget(e.target.value)}
            placeholder="Target ($)"
            className="input-field w-28"
          />
          <input
            type="date"
            value={editDate}
            onChange={(e) => setEditDate(e.target.value)}
            className="input-field"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleEdit}
            disabled={!editName.trim() || !editTarget}
            className="btn-action disabled:opacity-40"
          >
            Save
          </button>
          <button
            onClick={() => setEditing(false)}
            className="px-3 py-1.5 text-sm border border-border rounded-md text-muted hover:text-foreground transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="py-4 border-b border-border last:border-b-0 space-y-3">
      <div className="flex items-start gap-4">
        <ProgressRing percent={g.percent} />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-foreground">{g.name}</p>
              {g.target_date && (
                <p className="text-xs text-muted">Deadline: {g.target_date}</p>
              )}
            </div>
            {onTrackLabel && (
              <span className={`text-xs shrink-0 ${onTrackColor}`}>{onTrackLabel}</span>
            )}
          </div>
          <p className="text-sm text-foreground mt-1">
            ${g.saved_amount.toFixed(0)} saved of ${g.target_amount.toFixed(0)}
          </p>
          {g.monthly_rate > 0 && (
            <p className="text-xs text-muted mt-0.5">
              ~${g.monthly_rate.toFixed(0)}/mo
              {g.months_to_target != null && ` · ${g.months_to_target.toFixed(0)} months to target`}
            </p>
          )}
        </div>
      </div>

      {/* Sparkline: last 6 months contributions */}
      {g.contributions.length > 0 && (
        <div className="flex items-end gap-1 h-8">
          {(() => {
            const last6 = g.contributions.slice(-6);
            const maxAmt = Math.max(...last6.map((x) => x.amount), 1);
            return last6.map((c) => {
              const h = Math.max(4, (c.amount / maxAmt) * 32);
              return (
                <div
                  key={c.id}
                  title={`${c.month}: $${c.amount}`}
                  className="flex-1 rounded-sm bg-foreground/20 hover:bg-foreground/40 transition-colors"
                  style={{ height: `${h}px` }}
                />
              );
            });
          })()}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => { setContributing(!contributing); setEditing(false); }}
          className="text-xs px-2.5 py-1 border border-border rounded-md text-muted hover:text-foreground transition-colors"
        >
          + Add Contribution
        </button>
        <button
          onClick={startEdit}
          className="text-xs px-2.5 py-1 border border-border rounded-md text-muted hover:text-foreground transition-colors"
        >
          <Pencil className="w-3.5 h-3.5 inline mr-1" />
          Edit
        </button>
        <button
          onClick={() => {
            if (window.confirm(`Delete goal "${g.name}"? This will also remove all contribution history.`)) {
              onDelete(g.id);
            }
          }}
          className="text-xs px-2.5 py-1 border border-border rounded-md text-destructive hover:text-destructive/70 transition-colors"
        >
          <Trash2 className="w-3.5 h-3.5 inline mr-1" />
          Delete
        </button>
      </div>

      {contributing && (
        <div className="flex flex-wrap gap-2 pt-1">
          <input
            type="number"
            value={contribAmount}
            onChange={(e) => setContribAmount(e.target.value)}
            placeholder="Amount"
            className="input-field w-28"
          />
          <input
            type="text"
            value={contribNote}
            onChange={(e) => setContribNote(e.target.value)}
            placeholder="Note (optional)"
            className="input-field flex-1"
          />
          <button
            onClick={handleContrib}
            disabled={!contribAmount}
            className="btn-action disabled:opacity-40"
          >
            Save
          </button>
        </div>
      )}
    </div>
  );
}

function GoalsSection() {
  const qc = useQueryClient();
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newTarget, setNewTarget] = useState('');
  const [newDate, setNewDate] = useState('');

  const { data: goals = [], isLoading } = useQuery({
    queryKey: ['goals'],
    queryFn: () => api.getGoals(),
    staleTime: 30_000,
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createGoal({
        name: newName,
        target_amount: parseFloat(newTarget),
        target_date: newDate || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['goals'] });
      setShowAddForm(false);
      setNewName('');
      setNewTarget('');
      setNewDate('');
    },
  });

  const editMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { name?: string; target_amount?: number; target_date?: string } }) =>
      api.updateGoal(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['goals'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteGoal(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['goals'] }),
  });

  const contribMutation = useMutation({
    mutationFn: ({ id, amount, note }: { id: number; amount: number; note?: string }) =>
      api.contributeToGoal(id, { amount, note }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['goals'] }),
  });

  return (
    <PageCard
      title="Goals"
      action={
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="text-xs px-2.5 py-1 border border-border rounded-md text-muted hover:text-foreground transition-colors"
        >
          {showAddForm ? 'Cancel' : '+ Add Goal'}
        </button>
      }
    >
      {isLoading ? (
        <p className="text-muted text-sm py-4 text-center">Loading…</p>
      ) : goals.length === 0 ? (
        <p className="text-muted text-sm py-4 text-center">
          No goals yet. Add one to start tracking your savings.
        </p>
      ) : (
        goals.map((g) => (
          <GoalCard
            key={g.id}
            g={g}
            onContribute={(id, amount, note) => contribMutation.mutate({ id, amount, note })}
            onEdit={(id, data) => editMutation.mutate({ id, data })}
            onDelete={(id) => deleteMutation.mutate(id)}
          />
        ))
      )}
      {showAddForm && (
        <div className="pt-4 border-t border-border space-y-3">
          <p className="text-sm font-medium text-foreground">Add Goal</p>
          <div className="flex flex-wrap gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Goal name"
              className="input-field flex-1 min-w-40"
            />
            <input
              type="number"
              value={newTarget}
              onChange={(e) => setNewTarget(e.target.value)}
              placeholder="Target ($)"
              className="input-field w-28"
            />
            <input
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              className="input-field"
            />
          </div>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!newName || !newTarget || createMutation.isPending}
            className="btn-action disabled:opacity-40"
          >
            {createMutation.isPending ? 'Creating…' : 'Create Goal'}
          </button>
        </div>
      )}
    </PageCard>
  );
}

export function FinancePage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [showAddForm, setShowAddForm] = useState(false);

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
    staleTime: 10_000,
  });

  const { data: progress = [], isLoading } = useQuery({
    queryKey: ['budget-progress'],
    queryFn: () => api.getBudgetProgress(),
    enabled: settings?.budgets_enabled === true,
    staleTime: 30_000,
  });

  const { data: categories = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.getCategories(),
    staleTime: 60_000,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteBudget(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['budget-progress'] }),
  });

  const editMutation = useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: number }) =>
      api.updateBudget(id, amount),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['budget-progress'] }),
  });

  if (!settings) return null;

  if (!settings.budgets_enabled && !settings.goals_enabled) {
    return (
      <div className="p-6 flex flex-col items-center justify-center min-h-48 text-center gap-3">
        <p className="text-muted text-sm">
          Enable Budgets or Goals in Settings to get started.
        </p>
        <button
          onClick={() => navigate('/settings')}
          className="text-sm underline underline-offset-2 text-foreground/70 hover:text-foreground"
        >
          Go to Settings →
        </button>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6 max-w-2xl mx-auto">
      <h1 className="text-xl font-bold text-foreground">Finance</h1>

      {/* Budgets section */}
      {settings.budgets_enabled && (
      <PageCard
        title="Budgets"
        action={
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="text-xs px-2.5 py-1 border border-border rounded-md text-muted hover:text-foreground transition-colors"
          >
            {showAddForm ? 'Cancel' : '+ Add Budget'}
          </button>
        }
      >
        {isLoading ? (
          <p className="text-muted text-sm py-4 text-center">Loading…</p>
        ) : progress.length === 0 ? (
          <p className="text-muted text-sm py-4 text-center">
            No budgets yet. Add one to start tracking.
          </p>
        ) : (
          progress.map((b) => (
            <BudgetRow
              key={b.id}
              b={b}
              onDelete={(id) => deleteMutation.mutate(id)}
              onEdit={(id, amount) => editMutation.mutate({ id, amount })}
            />
          ))
        )}
        {showAddForm && (
          <AddBudgetForm
            categories={categories}
            onAdd={() => setShowAddForm(false)}
          />
        )}
      </PageCard>
      )}

      {/* Goals section — only when goals_enabled */}
      {settings.goals_enabled && (
        <GoalsSection />
      )}
    </div>
  );
}
