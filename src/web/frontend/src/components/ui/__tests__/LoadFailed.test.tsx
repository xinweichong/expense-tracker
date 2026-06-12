import { test, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { LoadFailed } from '../LoadFailed';

test('shows voice-conformant message and calls onRetry', () => {
  const onRetry = vi.fn();
  render(<LoadFailed onRetry={onRetry} />);
  expect(screen.getByText("Couldn't load this — try refreshing.")).toBeTruthy();
  fireEvent.click(screen.getByText('Retry'));
  expect(onRetry).toHaveBeenCalledTimes(1);
});
