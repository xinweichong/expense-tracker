import { test, expect } from 'vitest';
import { render } from '@testing-library/react';
import { Skeleton } from '../skeleton';
import { TransactionList } from '@/components/transactions/TransactionList';

test('renders a pulse block and merges custom classes', () => {
  const { container } = render(<Skeleton className="h-4 w-32" />);
  const el = container.firstElementChild as HTMLElement;
  expect(el.className).toContain('animate-pulse');
  expect(el.className).toContain('h-4');
  expect(el.className).toContain('w-32');
});

test('TransactionList shows skeleton rows on initial load', () => {
  const { getAllByTestId } = render(
    <TransactionList
      transactions={[]}
      onLoadMore={() => {}}
      hasMore={false}
      isLoading={true}
      onTransactionClick={() => {}}
    />
  );
  expect(getAllByTestId('tx-skeleton')).toHaveLength(8);
});
