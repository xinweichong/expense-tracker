import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number, currency = 'SGD'): string {
  return new Intl.NumberFormat('en-SG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(date: string): string {
  const [y, m, d] = date.split('T')[0].split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-SG', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

export function formatShortDate(date: string): string {
  const [y, m, d] = date.split('T')[0].split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-SG', {
    day: 'numeric',
    month: 'short',
  });
}

const CATEGORY_COLORS: Record<string, string> = {
  'Food': '#FF6B6B',
  'Food \ud83c\udf5c': '#FF6B6B',
  'Transport': '#64D2FF',
  'Transport \ud83d\ude97': '#64D2FF',
  'Shopping': '#BF5AF2',
  'Shopping \ud83d\uded2': '#BF5AF2',
  'Bills': '#FFD60A',
  'Bills \ud83d\udcc4': '#FFD60A',
  'Entertainment': '#30D158',
  'Entertainment \ud83c\udfac': '#30D158',
  'Other': '#72727E',
  'Other \ud83d\udccc': '#72727E',
  'Income': '#34C759',
};

export function getCategoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? '#72727E';
}
