import type { CSSProperties } from 'react';

export const CHART_TOOLTIP_STYLE: CSSProperties = {
  background: '#161624',
  border: '1px solid #2A2A3F',
  borderRadius: '8px',
  fontSize: '13px',
};

export const CHART_AXIS_PROPS = {
  tick: { fontSize: 11, fill: '#7A7488' },
  tickLine: false,
  axisLine: false,
};

export const CHART_CURSOR_BAR = { fill: '#1C1C22' };
export const CHART_CURSOR_LINE = { stroke: '#2A2A3F', strokeWidth: 1 };

export const CHART_LEGEND_STYLE: CSSProperties = {
  fontSize: '12px',
  color: '#7A7488',
};

// Spectrum data colors
export const COLOR_TEAL      = '#00D4AA';
export const COLOR_MINT      = '#34D399';
export const COLOR_HONEY     = '#FBBF24';
export const COLOR_TANGERINE = '#FB923C';
export const COLOR_CORAL     = '#FF6B6B';
export const COLOR_MUTED_BAR = '#3A3A46';

// Legacy aliases (kept for migration; remove in Phase 4)
export const COLOR_ACCENT  = COLOR_TEAL;
export const COLOR_INCOME  = COLOR_TEAL;
export const COLOR_EXPENSE = '#FF453A';

// 10-color cohesive palette sampled along the spectrum.
// Used for category fills (donut chart, category pills).
export const SPECTRUM_PALETTE = [
  '#00D4AA', '#2DD4BF', '#34D399', '#84CC16', '#EAB308',
  '#FBBF24', '#F97316', '#FB923C', '#FB7185', '#FF6B6B',
];

/** XAxis tick: show day-of-month only (e.g. "15") */
export function formatDateTick(v: string): string {
  return new Date(v).getDate().toString();
}

/** Tooltip label: short date (e.g. "15 Apr") */
export function formatDateLabel(v: unknown): string {
  return new Date(String(v)).toLocaleDateString('en-SG', { day: 'numeric', month: 'short' });
}
