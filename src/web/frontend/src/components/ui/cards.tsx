import type { CSSProperties, ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { motion } from 'framer-motion';
import { springs } from '@/lib/animations';

// ── PageCard ──────────────────────────────────────────────────────────────────
interface PageCardProps {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  contentClassName?: string;
}

export function PageCard({ title, action, children, className, contentClassName }: PageCardProps) {
  return (
    <Card className={cn(className)}>
      <div className="flex flex-row items-center justify-between p-4 gap-2">
        <span className="min-w-0 truncate text-base font-semibold text-foreground">{title}</span>
        {action && <div className="shrink-0 ml-2">{action}</div>}
      </div>
      <CardContent className={cn('p-4 pt-0', contentClassName)}>{children}</CardContent>
    </Card>
  );
}

// ── ChartCard ─────────────────────────────────────────────────────────────────
interface ChartCardProps {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function ChartCard({ title, action, children, className }: ChartCardProps) {
  return (
    <Card className={cn(className)}>
      <div className="flex flex-row items-center justify-between p-4 gap-2">
        <span className="min-w-0 truncate text-base font-semibold text-foreground">{title}</span>
        {action && <div className="shrink-0 ml-2">{action}</div>}
      </div>
      <CardContent className="p-0">{children}</CardContent>
    </Card>
  );
}

// ── StatCard ──────────────────────────────────────────────────────────────────
type StatVariant = 'expense' | 'income' | 'neutral';

const VARIANT_CLASS: Record<StatVariant, string> = {
  expense: 'text-destructive',
  income: 'text-success',
  neutral: 'text-foreground',
};

interface StatCardProps {
  label: string;
  value: ReactNode;
  variant?: StatVariant;
}

export function StatCard({ label, value, variant = 'neutral' }: StatCardProps) {
  const fontSizeClass =
    typeof value === 'string' && value.length >= 10 ? 'text-lg' :
    typeof value === 'string' && value.length >= 8  ? 'text-xl' :
    'text-2xl';

  return (
    <motion.div whileHover={{ y: -2 }} transition={springs.snappy}>
      <Card>
        <CardHeader className="pb-1">
          <CardTitle className="text-sm font-medium text-muted">{label}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={cn(fontSizeClass, 'font-bold truncate', VARIANT_CLASS[variant])}>{value}</p>
        </CardContent>
      </Card>
    </motion.div>
  );
}

// ── HeroCard ─────────────────────────────────────────────────────────────────
interface HeroCardProps {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

const HERO_CARD_STYLE: CSSProperties = {
  borderRadius: '24px',
  boxShadow: '0 0 0 1px rgba(251,146,60,.14), 0 0 48px -10px rgba(251,146,60,.34)',
  background:
    'radial-gradient(120% 100% at 100% 0%, rgba(251,146,60,.08) 0%, rgba(11,11,20,0) 50%), #161624',
  position: 'relative',
  overflow: 'hidden',
  padding: '32px',
};

const HERO_CARD_HAIRLINE_STYLE: CSSProperties = {
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  height: '1px',
  background:
    'linear-gradient(90deg, transparent, rgba(251,146,60,.32) 30%, rgba(255,107,107,.32) 70%, transparent)',
};

export function HeroCard({ title, action, children, className }: HeroCardProps) {
  return (
    <div style={HERO_CARD_STYLE} className={cn(className)}>
      <div style={HERO_CARD_HAIRLINE_STYLE} aria-hidden />
      <div className="flex flex-row items-center justify-between gap-2 mb-3">
        <span className="text-xs uppercase tracking-[0.22em] text-muted font-semibold font-mono">
          {title}
        </span>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {children}
    </div>
  );
}

// ── HighlightCard ─────────────────────────────────────────────────────────────
interface HighlightCardProps {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

const HIGHLIGHT_CARD_STYLE: CSSProperties = {
  border: '1px solid rgba(0,212,170,.25)',
  background:
    'radial-gradient(120% 100% at 0% 0%, rgba(0,212,170,.08) 0%, rgba(11,11,20,0) 50%), #161624',
  boxShadow: '0 0 0 1px rgba(0,212,170,.18), 0 0 36px -8px rgba(0,212,170,.28)',
  borderRadius: '14px',
  padding: '20px',
};

export function HighlightCard({ title, action, children, className }: HighlightCardProps) {
  return (
    <div style={HIGHLIGHT_CARD_STYLE} className={cn(className)}>
      <div className="flex flex-row items-center justify-between gap-2 mb-3">
        <span className="text-xs uppercase tracking-[0.22em] font-semibold font-mono" style={{ color: '#00D4AA' }}>
          {title}
        </span>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {children}
    </div>
  );
}
