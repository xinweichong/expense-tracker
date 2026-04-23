import { useState, useCallback } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { TransactionList } from '@/components/transactions/TransactionList';
import { TransactionFilters } from '@/components/transactions/TransactionFilters';
import { useCategories } from '@/hooks/useCategories';
import { api, type Transaction } from '@/api/client';
import { Plus } from 'lucide-react';
import { TransactionForm } from '@/components/transactions/TransactionForm';

const PAGE_SIZE = 20;

export function TransactionsPage() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [showForm, setShowForm] = useState(false);
  const { data: categories } = useCategories();

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
  } = useInfiniteQuery({
    queryKey: ['transactions', search, category, startDate, endDate],
    queryFn: ({ pageParam = 0 }) => {
      const params: Record<string, string | number> = {
        limit: PAGE_SIZE,
        offset: pageParam as number,
      };
      if (search) params.merchant = search;
      if (category && category !== 'all') params.category = category;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      return api.getTransactions(params);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage: Transaction[], allPages: Transaction[][]) => {
      if (lastPage.length < PAGE_SIZE) return undefined;
      return allPages.length * PAGE_SIZE;
    },
  });

  const txs = data?.pages.flat() ?? [];

  const handleCategoryChange = useCallback((v: string) => {
    setCategory(v);
  }, []);

  const handleSearchChange = useCallback((v: string) => {
    setSearch(v);
  }, []);

  const loadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

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
        startDate={startDate}
        setStartDate={setStartDate}
        endDate={endDate}
        setEndDate={setEndDate}
      />

      {showForm && (
        <TransactionForm
          categories={categories ?? []}
          onClose={() => setShowForm(false)}
        />
      )}

      <Card className="overflow-hidden">
        <TransactionList
          transactions={txs}
          onLoadMore={loadMore}
          hasMore={!!hasNextPage}
          isLoading={isLoading || isFetchingNextPage}
        />
      </Card>
    </div>
  );
}
