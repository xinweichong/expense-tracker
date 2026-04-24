import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { BottomTabs } from './BottomTabs';
import { CasheLogo } from '@/components/ui/CasheLogo';

export function AppShell() {
  return (
    <div className="min-h-screen bg-background flex">
      <Sidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Mobile-only top bar — hidden on md+ where sidebar provides branding */}
        <header className="md:hidden sticky top-0 z-40 h-12 shrink-0 bg-card border-b border-border flex items-center px-4 gap-2">
          <CasheLogo size={24} />
          <span className="text-base font-bold text-foreground tracking-tight">Cashe</span>
        </header>
        <main className="flex-1 min-w-0 pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
          <Outlet />
        </main>
      </div>
      <BottomTabs />
    </div>
  );
}
