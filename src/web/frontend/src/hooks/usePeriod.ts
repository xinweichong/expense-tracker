import { useState, useCallback } from 'react';

export type Period = 'day' | 'week' | 'month';

export function usePeriod() {
  const [period, setPeriod] = useState<Period>('month');
  const [date, setDate] = useState(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  });

  const goBack = useCallback(() => {
    const [y, mo, dy] = date.split('-').map(Number);
    const d = new Date(y, mo - 1, dy); // local time, not UTC
    if (period === 'day') d.setDate(d.getDate() - 1);
    else if (period === 'week') d.setDate(d.getDate() - 7);
    else d.setMonth(d.getMonth() - 1);
    setDate(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
  }, [date, period]);

  const goForward = useCallback(() => {
    const [y, mo, dy] = date.split('-').map(Number);
    const d = new Date(y, mo - 1, dy); // local time, not UTC
    if (period === 'day') d.setDate(d.getDate() + 1);
    else if (period === 'week') d.setDate(d.getDate() + 7);
    else d.setMonth(d.getMonth() + 1);
    setDate(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
  }, [date, period]);

  const goToToday = useCallback(() => {
    const d = new Date();
    setDate(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
  }, []);

  return { period, setPeriod, date, goBack, goForward, goToToday };
}
