import { test, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDebouncedValue } from '../useDebouncedValue';

test('holds the old value until the delay elapses', () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(
    ({ v }) => useDebouncedValue(v, 300),
    { initialProps: { v: 'a' } }
  );
  rerender({ v: 'ab' });
  expect(result.current).toBe('a');
  act(() => { vi.advanceTimersByTime(299); });
  expect(result.current).toBe('a');
  act(() => { vi.advanceTimersByTime(1); });
  expect(result.current).toBe('ab');
  vi.useRealTimers();
});
