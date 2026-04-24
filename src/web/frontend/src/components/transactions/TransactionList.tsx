import { useEffect, useRef } from 'react';
import { type Transaction } from '@/api/client';
import { TransactionRow } from './TransactionRow';

interface TransactionListProps {
  transactions: Transaction[];
  onLoadMore: () => void;
  hasMore: boolean;
  isLoading: boolean;
  onTransactionClick: (tx: Transaction) => void;
  selectedTransactionId?: number;
}

export function TransactionList({
  transactions,
  onLoadMore,
  hasMore,
  isLoading,
  onTransactionClick,
  selectedTransactionId,
}: TransactionListProps) {
  const observerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!hasMore || isLoading) return;
    const el = observerRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) onLoadMore(); },
      { rootMargin: '200px' },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, isLoading, onLoadMore]);

  if (transactions.length === 0 && !isLoading) {
    return (
      <div className="py-12 text-center text-muted text-sm">
        No transactions found
      </div>
    );
  }

  return (
    <div>
      {transactions.map((tx) => (
        <TransactionRow
          key={tx.id}
          tx={tx}
          onClick={() => onTransactionClick(tx)}
          selected={tx.id === selectedTransactionId}
        />
      ))}
      {hasMore && (
        <div ref={observerRef} className="py-4 text-center text-muted text-xs">
          {isLoading ? 'Loading...' : 'Load more'}
        </div>
      )}
    </div>
  );
}
