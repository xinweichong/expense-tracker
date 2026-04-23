import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

// ── PageCard ──────────────────────────────────────────────────────────────────
interface PageCardProps {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function PageCard({ title, action, children, className }: PageCardProps) {
  return (
    <Card className={cn(className)}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium">{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent>{children}</CardContent>
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
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium">{title}</CardTitle>
        {action}
      </CardHeader>
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
  value: string;
  variant?: StatVariant;
}

export function StatCard({ label, value, variant = 'neutral' }: StatCardProps) {
  return (
    <Card>
      <CardHeader className="pb-1">
        <CardTitle className="text-sm font-medium text-muted">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className={cn('text-2xl font-bold', VARIANT_CLASS[variant])}>{value}</p>
      </CardContent>
    </Card>
  );
}
