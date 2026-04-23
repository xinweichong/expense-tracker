import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { LayoutDashboard, List, BarChart3, Settings, MoreHorizontal, Store, X } from 'lucide-react';

// Spec order: Overview | Transactions | Analytics | More(⋯) | Settings
// Settings is a direct bottom tab (5th position), More is 4th.
const primaryTabs = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/transactions', icon: List, label: 'Transactions' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
];

export function BottomTabs() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();

  const handleMoreItemClick = (to: string) => {
    setDrawerOpen(false);
    navigate(to);
  };

  return (
    <>
      {/* More drawer overlay */}
      {drawerOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/50 z-40"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      {/* More drawer panel */}
      {drawerOpen && (
        <div className="md:hidden fixed bottom-16 left-0 right-0 bg-card border-t border-border z-50 rounded-t-xl shadow-lg">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <span className="text-sm font-medium text-foreground">More</span>
            <button onClick={() => setDrawerOpen(false)}>
              <X className="w-4 h-4 text-muted" />
            </button>
          </div>
          <div className="py-2">
            <button
              onClick={() => handleMoreItemClick('/merchants')}
              className="w-full flex items-center gap-3 px-4 py-3 text-sm text-foreground hover:bg-foreground/5 transition-colors"
            >
              <Store className="w-5 h-5 text-muted" />
              Merchants
            </button>
          </div>
        </div>
      )}

      {/* Bottom tab bar — spec order: Overview | Transactions | Analytics | More(⋯) | Settings */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card border-t border-border flex justify-around items-center h-16 z-50">
        {primaryTabs.map(({ to, icon: Icon, label }) => (
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
        <button
          onClick={() => setDrawerOpen(!drawerOpen)}
          className="flex flex-col items-center gap-0.5 px-3 py-1.5 text-xs text-muted"
        >
          <MoreHorizontal className="w-5 h-5" />
          <span>More</span>
        </button>
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
    </>
  );
}
