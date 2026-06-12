import { Button } from '@/components/ui/button';

export function LoadFailed({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="py-8 flex flex-col items-center gap-3 text-center">
      <p className="text-sm text-muted">Couldn't load this — try refreshing.</p>
      <Button variant="ghost" size="sm" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
