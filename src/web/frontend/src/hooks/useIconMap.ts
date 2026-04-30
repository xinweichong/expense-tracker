import { useMemo } from 'react';
import { useCategories } from '@/hooks/useCategories';

/** Returns a map of { categoryName: icon } for all categories. */
export function useIconMap(): Record<string, string> {
  const { data: categories } = useCategories();
  return useMemo(
    () => Object.fromEntries((categories ?? []).map(c => [c.name, c.icon ?? ''])),
    [categories],
  );
}
