import type { CSSProperties } from 'react';

export const CHART_TOOLTIP_STYLE: CSSProperties = {
  background: '#16161A',
  border: '1px solid #2A2A32',
  borderRadius: '8px',
  fontSize: '13px',
};

export const CHART_AXIS_PROPS = {
  tick: { fontSize: 11, fill: '#72727E' },
  tickLine: false,
  axisLine: false,
};

export const CHART_CURSOR_BAR = { fill: '#1C1C22' };
export const CHART_CURSOR_LINE = { stroke: '#2A2A32', strokeWidth: 1 };

export const CHART_LEGEND_STYLE: CSSProperties = {
  fontSize: '12px',
  color: '#72727E',
};

export const COLOR_INCOME = '#30D158';    // --color-success
export const COLOR_EXPENSE = '#FF453A';   // --color-destructive
export const COLOR_ACCENT = '#00D4AA';    // --color-accent
export const COLOR_MUTED_BAR = '#3A3A46';

/** XAxis tick: show day-of-month only (e.g. "15") */
export function formatDateTick(v: string): string {
  return new Date(v).getDate().toString();
}

/** Tooltip label: short date (e.g. "15 Apr") */
export function formatDateLabel(v: unknown): string {
  return new Date(String(v)).toLocaleDateString('en-SG', { day: 'numeric', month: 'short' });
}
