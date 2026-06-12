import { test, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PullToRefresh } from '../PullToRefresh';

function setup() {
  const qc = new QueryClient();
  const spy = vi.spyOn(qc, 'refetchQueries').mockResolvedValue(undefined as never);
  render(
    <QueryClientProvider client={qc}>
      <PullToRefresh>
        <div>content</div>
      </PullToRefresh>
    </QueryClientProvider>
  );
  return { spy, surface: screen.getByTestId('ptr-surface') };
}

test('a long downward pull triggers a refetch of active queries', async () => {
  const { spy, surface } = setup();
  fireEvent.touchStart(surface, { touches: [{ clientY: 10 }] });
  fireEvent.touchMove(surface, { touches: [{ clientY: 160 }] });
  fireEvent.touchEnd(surface);
  await waitFor(() => expect(spy).toHaveBeenCalledWith({ type: 'active' }));
});

test('a short pull does not trigger', () => {
  const { spy, surface } = setup();
  fireEvent.touchStart(surface, { touches: [{ clientY: 10 }] });
  fireEvent.touchMove(surface, { touches: [{ clientY: 40 }] });
  fireEvent.touchEnd(surface);
  expect(spy).not.toHaveBeenCalled();
});
