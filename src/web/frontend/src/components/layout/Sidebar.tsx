import { NavLink } from 'react-router-dom';
import { LayoutDashboard, List, BarChart3, Store, Wallet, Settings, Lock } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';
import { CasheWordmark, CasheIcon } from '@/components/ui/Brand';

export function Sidebar() {
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
    staleTime: 30_000,
  });
  const financeEnabled =
    settings?.budgets_enabled ||
    settings?.goals_enabled ||
    settings?.trips_enabled ||
    settings?.subscriptions_enabled;

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Overview' },
    { to: '/transactions', icon: List, label: 'Transactions' },
    { to: '/analytics', icon: BarChart3, label: 'Analytics' },
    { to: '/merchants', icon: Store, label: 'Merchants' },
  ];

  return (
    <aside className="hidden md:flex flex-col w-14 lg:w-56 bg-card/80 backdrop-blur-sm border-r border-border h-screen sticky top-0">
      <div className="flex items-center justify-center lg:justify-start gap-3 px-3 py-5 lg:px-4">
        <CasheIcon size={32} className="lg:hidden" />
        <CasheWordmark size={22} className="hidden lg:inline-flex" />
      </div>
      <nav className="flex-1 px-2 lg:px-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors justify-center lg:justify-start ${
                isActive
                  ? 'bg-foreground/10 text-foreground font-medium'
                  : 'text-muted hover:text-foreground hover:bg-foreground/5'
              }`
            }
          >
            <Icon className="w-5 h-5 shrink-0" />
            <span className="hidden lg:inline font-display">{label}</span>
          </NavLink>
        ))}

        {/* Finance — always visible; dimmed when neither toggle is on */}
        <NavLink
          to="/finance"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors justify-center lg:justify-start ${
              isActive
                ? 'bg-foreground/10 text-foreground font-medium'
                : 'text-muted hover:text-foreground hover:bg-foreground/5'
            } ${!financeEnabled ? 'opacity-40' : ''}`
          }
        >
          <Wallet className="w-5 h-5 shrink-0" />
          <span className="hidden lg:flex items-center gap-1 font-display">
            Finance
            {!financeEnabled && <Lock className="w-3 h-3 ml-1" />}
          </span>
        </NavLink>

        {/* Settings — always last */}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors justify-center lg:justify-start ${
              isActive
                ? 'bg-foreground/10 text-foreground font-medium'
                : 'text-muted hover:text-foreground hover:bg-foreground/5'
            }`
          }
        >
          <Settings className="w-5 h-5 shrink-0" />
          <span className="hidden lg:inline font-display">Settings</span>
        </NavLink>
      </nav>
    </aside>
  );
}
