import { useState, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { TransactionList } from '@/components/transactions/TransactionList';
import { TransactionFilters } from '@/components/transactions/TransactionFilters';
import { useTransactions } from '@/hooks/useTransactions';
import { useCategories } from '@/hooks/useCategories';
import { Plus } from 'lucide-react';

const PAGE_SIZE = 20;

export function TransactionsPage() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [offset, setOffset] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const { data: categories } = useCategories();

  const params: Record<string, string | number> = {
    limit: PAGE_SIZE,
    offset,
  };
  if (search) params.merchant = search;
  if (category && category !== 'all') params.category = category;

  const { data: transactions, isLoading } = useTransactions(params);
  const txs = transactions ?? [];
  const hasMore = txs.length === PAGE_SIZE;

  const handleCategoryChange = (v: string) => {
    setCategory(v);
    setOffset(0);
  };

  const handleSearchChange = (v: string) => {
    setSearch(v);
    setOffset(0);
  };

  const loadMore = useCallback(() => {
    setOffset((prev) => prev + PAGE_SIZE);
  }, []);

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Transactions</h1>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          <Plus className="w-4 h-4 mr-1" />
          Add
        </Button>
      </div>

      <TransactionFilters
        search={search}
        onSearchChange={handleSearchChange}
        category={category}
        onCategoryChange={handleCategoryChange}
        categories={categories ?? []}
      />

      {showForm && (
        <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted">
          Transaction form coming soon (Task 9)
        </div>
      )}

      <Card className="bg-card border-border overflow-hidden">
        <TransactionList
          transactions={txs}
          onLoadMore={loadMore}
          hasMore={hasMore}
          isLoading={isLoading}
        />
      </Card>
    </div>
  );
}
