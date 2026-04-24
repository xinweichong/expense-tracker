import type { ReactNode } from 'react';
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
