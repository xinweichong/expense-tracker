import { CasheWordmark, B1_WASH } from '@/components/ui/Brand';

export function SplashScreen() {
  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center gap-6"
      style={{ background: B1_WASH }}
    >
      <CasheWordmark size={42} />
      <span className="text-xs text-muted font-mono uppercase tracking-[0.22em]">
        Catching up…
      </span>
    </div>
  );
}
