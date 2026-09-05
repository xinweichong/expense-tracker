/** Shared tag constants for merchant list and merchant profile views. */

export const TAG_COLORS: Record<string, string> = {
  online:       'bg-blue-500/20 text-blue-400 border-blue-500/30',
  subscription: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  foreign:      'bg-orange-500/20 text-orange-400 border-orange-500/30',
  essential:    'bg-amber-500/20 text-amber-400 border-amber-500/30',
  recurring:    'bg-teal-500/20 text-teal-400 border-teal-500/30',
};

export const ALL_TAGS: string[] = Object.keys(TAG_COLORS);

export function formatSGD(v: number): string {
  return `$${v.toLocaleString('en-SG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
