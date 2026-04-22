import { useState } from 'react';
import { type Transaction } from '@/api/client';
import { formatCurrency, formatDate, getCategoryColor } from '@/lib/utils';
import { useUpdateTransaction, useDeleteTransaction } from '@/hooks/useTransactions';
import { useCategories } from '@/hooks/useCategories';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Pencil, Trash2, Check, X as XIcon } from 'lucide-react';

export function TransactionRow({ tx }: { tx: Transaction }) {
  const [editing, setEditing] = useState(false);
  const [merchant, setMerchant] = useState(tx.merchant ?? '');
  const [category, setCategory] = useState(tx.category ?? '');
  const updateTx = useUpdateTransaction();
  const deleteTx = useDeleteTransaction();
  const { data: categories } = useCategories();

  const handleSave = () => {
    updateTx.mutate(
      { id: tx.id, data: { merchant, category } },
      { onSuccess: () => setEditing(false) }
    );
  };

  const handleDelete = () => {
    if (confirm('Delete this transaction?')) {
      deleteTx.mutate(tx.id);
    }
  };

  if (editing) {
    return (
      <div className="px-4 py-3 space-y-2 border-b border-border bg-card/50">
        <div className="flex gap-2">
          <Input
            value={merchant}
            onChange={(e) => setMerchant(e.target.value)}
            placeholder="Merchant"
            className="bg-background border-border text-sm"
          />
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-40 bg-background border-border text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {categories?.map((cat) => (
                <SelectItem key={cat.name} value={cat.name}>{cat.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex gap-2 justify-end">
          <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
            <XIcon className="w-4 h-4" />
          </Button>
          <Button size="sm" onClick={handleSave} disabled={updateTx.isPending}>
            <Check className="w-4 h-4" />
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="group px-4 py-3 flex items-center gap-3 border-b border-border hover:bg-card/50 transition-colors last:border-b-0">
      <div className="w-1 h-8 rounded-full shrink-0" style={{ backgroundColor: getCategoryColor(tx.category ?? '') }} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{tx.merchant || tx.description || 'Transaction'}</p>
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-xs text-muted">{formatDate(tx.transaction_date)}</p>
          {tx.category && (
            <Badge variant="outline" className="text-xs px-1.5 py-0 h-4 border-border">
              {tx.category}
            </Badge>
          )}
          {tx.currency !== 'SGD' && (
            <Badge variant="outline" className="text-xs px-1.5 py-0 h-4 border-border">
              {tx.currency}
            </Badge>
          )}
        </div>
      </div>
      <span className={`text-sm font-semibold whitespace-nowrap ${tx.type === 'income' ? 'text-success' : ''}`}>
        {tx.type === 'income' ? '+' : '-'}{formatCurrency(tx.amount, tx.currency)}
      </span>
      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setEditing(true)}>
          <Pencil className="w-3.5 h-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7 text-accent" onClick={handleDelete}>
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
}
