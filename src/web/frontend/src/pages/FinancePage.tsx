import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api, type BudgetProgress, type Category } from '@/api/client';
import { PageCard } from '@/components/ui/cards';
import { cn } from '@/lib/utils';

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
          className={cn('input-field', 'flex-1 min-w-32')}
        >
          <option value="__overall__">Overall</option>
          {categories.map((c) => (
            <option key={c.name} value={c.name}>{c.name}</option>
          ))}
        </select>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="input-field"
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

  if (!settings.budgets_enabled) {
    return (
      <div className="p-6 flex flex-col items-center justify-center min-h-48 text-center gap-3">
        <p className="text-muted text-sm">
          Budgets are disabled. Enable them in Settings to get started.
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
    </div>
  );
}
