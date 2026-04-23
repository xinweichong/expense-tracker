import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, List, BarChart3, Settings,
  MoreHorizontal, Store, Wallet, X, Lock,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';

export function BottomTabs() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
    staleTime: 30_000,
  });

  const handleMoreItemClick = (to: string) => {
    setDrawerOpen(false);
    navigate(to);
  };

  const mainTabs = [
    { to: '/', icon: LayoutDashboard, label: 'Overview' },
    { to: '/transactions', icon: List, label: 'Transactions' },
    { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  ];

  return (
    <>
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card border-t border-border flex justify-around items-center h-16 z-50">
        {mainTabs.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-3 py-1.5 text-xs transition-colors ${
                isActive ? 'text-foreground' : 'text-muted'
              }`
            }
          >
            <Icon className="w-5 h-5" />
            <span>{label}</span>
          </NavLink>
        ))}

        {/* More button */}
        <button
          onClick={() => setDrawerOpen(true)}
          className="flex flex-col items-center gap-0.5 px-3 py-1.5 text-xs text-muted"
        >
          <MoreHorizontal className="w-5 h-5" />
          <span>More</span>
        </button>

        {/* Settings */}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 px-3 py-1.5 text-xs transition-colors ${
              isActive ? 'text-foreground' : 'text-muted'
            }`
          }
        >
          <Settings className="w-5 h-5" />
          <span>Settings</span>
        </NavLink>
      </nav>

      {/* More Drawer */}
      {drawerOpen && (
        <>
          {/* Backdrop */}
          <div
            className="md:hidden fixed inset-0 bg-background/60 z-50"
            onClick={() => setDrawerOpen(false)}
          />
          {/* Panel */}
          <div className="md:hidden fixed bottom-0 left-0 right-0 bg-card border-t border-border rounded-t-xl z-50">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="text-sm font-medium text-foreground">More</span>
              <button onClick={() => setDrawerOpen(false)}>
                <X className="w-5 h-5 text-muted" />
              </button>
            </div>
            {/* Merchants — always visible (Phase 2a) */}
            <button
              onClick={() => handleMoreItemClick('/merchants')}
              className="w-full flex items-center gap-3 px-4 py-3 text-sm text-foreground hover:bg-foreground/5 transition-colors"
            >
              <Store className="w-5 h-5 text-muted" />
              Merchants
            </button>
            {/* Finance — always visible, dimmed with lock icon when disabled */}
            {settings?.budgets_enabled ? (
              <button
                onClick={() => handleMoreItemClick('/finance')}
                className="w-full flex items-center gap-3 px-4 py-3 text-sm text-foreground hover:bg-foreground/5 transition-colors"
              >
                <Wallet className="w-5 h-5 text-muted" />
                Finance
              </button>
            ) : (
              <button
                onClick={() => handleMoreItemClick('/settings')}
                className="w-full flex items-center gap-3 px-4 py-3 text-sm text-muted/40 hover:text-muted/60 hover:bg-foreground/5 transition-colors"
                title="Enable Budgets in Settings"
              >
                <Wallet className="w-5 h-5" />
                Finance
                <Lock className="w-3 h-3 ml-auto shrink-0" />
              </button>
            )}
          </div>
        </>
      )}
    </>
  );
}
