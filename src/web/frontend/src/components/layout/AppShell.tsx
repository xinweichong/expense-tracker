import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { BottomTabs } from './BottomTabs';

export function AppShell() {
  return (
    <div className="min-h-screen bg-background flex">
      <Sidebar />
      <main className="flex-1 min-w-0 pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
        <Outlet />
      </main>
      <BottomTabs />
    </div>
  );
}
