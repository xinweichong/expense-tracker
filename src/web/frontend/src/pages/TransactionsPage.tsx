import { useState, useCallback } from 'react';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { TransactionList } from '@/components/transactions/TransactionList';
import { TransactionFilters } from '@/components/transactions/TransactionFilters';
import { TransactionDetail } from '@/components/transactions/TransactionDetail';
import { TransactionForm } from '@/components/transactions/TransactionForm';
import { useCategories } from '@/hooks/useCategories';
import { api, type Transaction } from '@/api/client';
import { slideInRightVariants, fadeUpVariants } from '@/lib/animations';
import { Plus } from 'lucide-react';

const PAGE_SIZE = 20;

export function TransactionsPage() {
  const navigate = useNavigate();
  const { transactionId } = useParams<{ transactionId?: string }>();
  const parsed = transactionId ? parseInt(transactionId, 10) : NaN;
  const selectedId = isNaN(parsed) ? undefined : parsed;

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [showForm, setShowForm] = useState(false);
  const { data: categories } = useCategories();

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery({
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

  // Use list data if available — only hit the single-tx endpoint for deep-links
  // where the transaction isn't in the loaded pages (e.g. direct URL navigation)
  const txFromList = selectedId !== undefined
    ? txs.find((tx) => tx.id === selectedId)
    : undefined;

  const { data: txFromQuery } = useQuery({
    queryKey: ['transaction', selectedId],
    queryFn: () => api.getTransaction(selectedId!),
    enabled: selectedId !== undefined && txFromList === undefined,
    staleTime: 30_000,
  });

  const selectedTransaction = txFromList ?? txFromQuery ?? null;

  const handleCategoryChange = useCallback((v: string) => setCategory(v), []);
  const handleSearchChange = useCallback((v: string) => setSearch(v), []);
  const loadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Toggle: clicking the active row navigates back to /transactions (closes panel)
  const handleTransactionClick = useCallback(
    (tx: Transaction) => {
      if (selectedId === tx.id) {
        navigate('/transactions');
      } else {
        navigate(`/transactions/${tx.id}`);
      }
    },
    [selectedId, navigate],
  );

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: transaction list — hidden on mobile when detail is open */}
      <div
        className={`flex-1 overflow-y-auto p-4 md:p-6 space-y-4 ${
          selectedTransaction ? 'hidden md:block' : ''
        }`}
      >
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
          <AnimatePresence>
            <motion.div
              variants={fadeUpVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <TransactionForm
                categories={categories ?? []}
                onClose={() => setShowForm(false)}
              />
            </motion.div>
          </AnimatePresence>
        )}

        <Card className="overflow-hidden">
          <TransactionList
            transactions={txs}
            onLoadMore={loadMore}
            hasMore={!!hasNextPage}
            isLoading={isLoading || isFetchingNextPage}
            onTransactionClick={handleTransactionClick}
            selectedTransactionId={selectedId}
          />
        </Card>
      </div>

      {/* Right: transaction detail panel */}
      <AnimatePresence>
        {selectedTransaction && (
          <motion.div
            className="w-full md:w-96 border-l border-border bg-card flex-shrink-0 overflow-hidden"
            variants={slideInRightVariants}
            initial="initial"
            animate="animate"
            exit="exit"
          >
            <TransactionDetail
              transaction={selectedTransaction}
              onClose={() => navigate('/transactions')}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
