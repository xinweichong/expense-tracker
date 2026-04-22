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

const DEFAULT_CATEGORY_COLORS: Record<string, string> = {
  'Food': '#FF6B6B',
  'Transport': '#64D2FF',
  'Shopping': '#BF5AF2',
  'Bills': '#FFD60A',
  'Entertainment': '#30D158',
  'Other': '#72727E',
  'Income': '#34C759',
};

// Runtime color overrides — populated when categories load from DB
const _categoryColorOverrides: Record<string, string> = {};

export function setCategoryColors(categories: { name: string; color: string | null }[]) {
  Object.keys(_categoryColorOverrides).forEach(k => delete _categoryColorOverrides[k]);
  for (const cat of categories) {
    if (cat.color) {
      _categoryColorOverrides[cat.name] = cat.color;
    }
  }
}

export function getCategoryColor(category: string): string {
  if (_categoryColorOverrides[category]) return _categoryColorOverrides[category];
  return DEFAULT_CATEGORY_COLORS[category] ?? '#72727E';
}

export const PALETTE = [
  '#FF6B6B', '#64D2FF', '#BF5AF2', '#FFD60A', '#30D158',
  '#FF9F0A', '#FF375F', '#7D7AFF', '#5AC8FA', '#FF6482',
  '#63E6BE', '#DAEFBD', '#B4A7FF', '#FFA07A', '#98D8C8',
  '#F7DC6F', '#BB8FCE', '#85C1E9', '#F0B27A', '#AED6F1',
];
