import { useState, useMemo } from 'react';
import { type Transaction } from '@/api/client';
import { formatCurrency, formatDateTime, getCategoryColor } from '@/lib/utils';
import { useCategories } from '@/hooks/useCategories';
import { Badge } from '@/components/ui/badge';

export function TransactionRow({
  tx,
  readOnly = false,
  onClick,
  selected = false,
}: {
  tx: Transaction;
  readOnly?: boolean;
  onClick?: () => void;
  selected?: boolean;
}) {
  const [hovered, setHovered] = useState(false);
  const { data: categories } = useCategories();
  const categoryColor = getCategoryColor(tx.category ?? '');

  const iconMap = useMemo(
    () => Object.fromEntries((categories ?? []).map(c => [c.name, c.icon ?? ''])),
    [categories],
  );
  const categoryIcon = tx.category ? (iconMap[tx.category] ?? [...tx.category][0] ?? '•') : '•';

  const isClickable = !readOnly && !!onClick;

  return (
    <div
      className={`px-4 py-3 flex items-center gap-3 border-b border-border transition-colors last:border-b-0 ${isClickable ? 'cursor-pointer' : ''}`}
      style={{ backgroundColor: `${categoryColor}${selected || hovered ? '1A' : '0D'}` }}
      onClick={isClickable ? onClick : undefined}
      onMouseEnter={isClickable ? () => setHovered(true) : undefined}
      onMouseLeave={isClickable ? () => setHovered(false) : undefined}
    >
      <div
        className="w-8 h-8 rounded-lg shrink-0 flex items-center justify-center text-base"
        style={{ backgroundColor: `${categoryColor}33` }}
      >
        {categoryIcon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">
          {tx.merchant || tx.description || 'Transaction'}
        </p>
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-xs text-muted">{formatDateTime(tx.transaction_date)}</p>
          {tx.category && (
            <Badge variant="outline" className="text-xs px-1.5 py-0 h-4 border-border">
              {tx.category}
            </Badge>
          )}
        </div>
      </div>
      <div className="text-right">
        <p className={`text-sm font-semibold whitespace-nowrap ${tx.type === 'income' ? 'text-success' : ''}`}>
          {tx.type === 'income' ? '+' : '-'}{formatCurrency(tx.amount, tx.currency)}
        </p>
      </div>
    </div>
  );
}
