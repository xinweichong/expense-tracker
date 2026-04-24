import { NavLink } from 'react-router-dom';
import { LayoutDashboard, List, BarChart3, Store, Wallet, Settings, Lock, Plane } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api/client';

export function Sidebar() {
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
    staleTime: 30_000,
  });
  const financeEnabled = settings?.budgets_enabled || settings?.goals_enabled;
  const tripsEnabled = settings?.trips_enabled;

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Overview' },
    { to: '/transactions', icon: List, label: 'Transactions' },
    { to: '/analytics', icon: BarChart3, label: 'Analytics' },
    { to: '/merchants', icon: Store, label: 'Merchants' },
  ];

  return (
    <aside className="hidden md:flex flex-col w-56 lg:w-64 bg-card border-r border-border h-screen sticky top-0">
      <div className="p-6">
        <h1 className="text-lg font-bold text-foreground">Expenses</h1>
      </div>
      <nav className="flex-1 px-3 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-foreground/10 text-foreground font-medium'
                  : 'text-muted hover:text-foreground hover:bg-foreground/5'
              }`
            }
          >
            <Icon className="w-5 h-5 shrink-0" />
            <span className="hidden lg:inline">{label}</span>
          </NavLink>
        ))}

        {/* Finance — always visible; dimmed when neither toggle is on */}
        <NavLink
          to="/finance"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
              isActive
                ? 'bg-foreground/10 text-foreground font-medium'
                : 'text-muted hover:text-foreground hover:bg-foreground/5'
            } ${!financeEnabled ? 'opacity-40' : ''}`
          }
        >
          <Wallet className="w-5 h-5 shrink-0" />
          <span className="hidden lg:flex items-center gap-1">
            Finance
            {!financeEnabled && <Lock className="w-3 h-3 ml-1 inline" />}
          </span>
        </NavLink>

        {/* Trips — always visible; dimmed when toggle is off */}
        <NavLink
          to="/trips"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
              isActive
                ? 'bg-foreground/10 text-foreground font-medium'
                : 'text-muted hover:text-foreground hover:bg-foreground/5'
            } ${!tripsEnabled ? 'opacity-40' : ''}`
          }
        >
          <Plane className="w-5 h-5 shrink-0" />
          <span className="hidden lg:flex items-center gap-1">
            Trips
            {!tripsEnabled && <Lock className="w-3 h-3 ml-1 inline" />}
          </span>
        </NavLink>

        {/* Settings — always last */}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
              isActive
                ? 'bg-foreground/10 text-foreground font-medium'
                : 'text-muted hover:text-foreground hover:bg-foreground/5'
            }`
          }
        >
          <Settings className="w-5 h-5 shrink-0" />
          <span className="hidden lg:inline">Settings</span>
        </NavLink>
      </nav>
    </aside>
  );
}
