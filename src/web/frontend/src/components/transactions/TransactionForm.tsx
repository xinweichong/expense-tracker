import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { useCreateTransaction } from '@/hooks/useTransactions';
import { type Category } from '@/api/client';

const TX_TYPES = [
  { value: 'expense', label: 'Expense' },
  { value: 'income', label: 'Income' },
  { value: 'cash', label: 'Cash' },
] as const;

type TxType = typeof TX_TYPES[number]['value'];

const CURRENCIES = ['SGD', 'USD', 'THB', 'MYR', 'JPY', 'EUR', 'GBP'] as const;

interface TransactionFormProps {
  categories: Category[];
  onClose: () => void;
}

export function TransactionForm({ categories, onClose }: TransactionFormProps) {
  const [type, setType] = useState<TxType>('expense');
  const [amount, setAmount] = useState('');
  const [merchant, setMerchant] = useState('');
  const [category, setCategory] = useState('');
  const [description, setDescription] = useState('');
  const [currency, setCurrency] = useState('SGD');
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0]);

  const createTx = useCreateTransaction();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createTx.mutate(
      {
        type,
        amount: parseFloat(amount),
        merchant: merchant || undefined,
        category: category || undefined,
        description: description || undefined,
        currency,
        source: type === 'cash' ? 'cash' : 'manual',
        transaction_date: date,
      },
      { onSuccess: onClose }
    );
  };

  return (
    <Card className="p-4 bg-card border-border">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex gap-1 bg-background rounded-lg p-1">
          {TX_TYPES.map((t) => (
            <Button
              key={t.value}
              type="button"
              variant={type === t.value ? 'secondary' : 'ghost'}
              size="sm"
              className="flex-1"
              onClick={() => setType(t.value)}
            >
              {t.label}
            </Button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-muted">Amount</label>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="bg-background border-border"
              required
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-muted">Currency</label>
            <Select value={currency} onValueChange={setCurrency}>
              <SelectTrigger className="bg-background border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CURRENCIES.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div>
          <label className="text-xs text-muted">Merchant</label>
          <Input
            value={merchant}
            onChange={(e) => setMerchant(e.target.value)}
            placeholder="e.g. Coffee Shop"
            className="bg-background border-border"
          />
        </div>

        <div>
          <label className="text-xs text-muted">Category</label>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="bg-background border-border">
              <SelectValue placeholder="Select category" />
            </SelectTrigger>
            <SelectContent>
              {categories.map((cat) => (
                <SelectItem key={cat.name} value={cat.name}>{cat.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <label className="text-xs text-muted">Date</label>
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="bg-background border-border"
          />
        </div>

        <div>
          <label className="text-xs text-muted">Description (optional)</label>
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Notes..."
            className="bg-background border-border"
          />
        </div>

        <Separator />

        <div className="flex gap-2 justify-end">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={!amount || createTx.isPending}>
            {createTx.isPending ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </form>
    </Card>
  );
}
