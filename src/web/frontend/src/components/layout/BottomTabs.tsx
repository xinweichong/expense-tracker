import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, List, BarChart3, Settings,
  MoreHorizontal, Store, Wallet, X, Lock, Plane,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { AnimatePresence, motion } from 'framer-motion';
import { api } from '@/api/client';
import { slideUpVariants } from '@/lib/animations';

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
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card/80 backdrop-blur-sm border-t border-border z-50">
        <div className="flex justify-around items-center h-16">
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
        </div>
        {/* Safe area spacer — extends the background below tab row on devices with curved corners */}
        <div className="h-[env(safe-area-inset-bottom)]" />
      </nav>

      {/* More Drawer */}
      <AnimatePresence>
        {drawerOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              className="md:hidden fixed inset-0 bg-background/60 z-50"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              onClick={() => setDrawerOpen(false)}
            />
            {/* Panel */}
            <motion.div
              className="md:hidden fixed bottom-0 left-0 right-0 bg-card border-t border-border rounded-t-xl z-50"
              variants={slideUpVariants}
              initial="initial"
              animate="animate"
              exit="exit"
            >
              <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                <span className="text-sm font-medium text-foreground">More</span>
                <button onClick={() => setDrawerOpen(false)}>
                  <X className="w-5 h-5 text-muted" />
                </button>
              </div>
              {/* Merchants — always visible */}
              <button
                onClick={() => handleMoreItemClick('/merchants')}
                className="w-full flex items-center gap-3 px-4 py-3 text-sm text-foreground hover:bg-foreground/5 transition-colors"
              >
                <Store className="w-5 h-5 text-muted" />
                Merchants
              </button>
              {/* Finance — always visible, dimmed with lock icon when disabled */}
              {(settings?.budgets_enabled || settings?.goals_enabled) ? (
                <button
                  onClick={() => handleMoreItemClick('/finance')}
                  className="w-full flex items-center gap-3 px-4 py-3 text-sm text-foreground hover:bg-foreground/5 transition-colors"
                >
                  <Wallet className="w-5 h-5 text-muted" />
                  Finance
                </button>
              ) : (
                <button
                  onClick={() => handleMoreItemClick('/settings#feature-toggles')}
                  className="w-full flex items-center gap-3 px-4 py-3 text-sm text-muted/40 hover:text-muted/60 hover:bg-foreground/5 transition-colors"
                  title="Enable Budgets or Goals in Settings"
                >
                  <Wallet className="w-5 h-5" />
                  Finance
                  <Lock className="w-3 h-3 ml-auto shrink-0" />
                </button>
              )}
              {/* Trips — always visible, locked when disabled */}
              {settings?.trips_enabled ? (
                <button
                  onClick={() => handleMoreItemClick('/trips')}
                  className="w-full flex items-center gap-3 px-4 py-3 text-sm text-foreground hover:bg-foreground/5 transition-colors"
                >
                  <Plane className="w-5 h-5 text-muted" />
                  Trips
                </button>
              ) : (
                <button
                  onClick={() => handleMoreItemClick('/settings#feature-toggles')}
                  className="w-full flex items-center gap-3 px-4 py-3 text-sm text-muted/40 hover:text-muted/60 hover:bg-foreground/5 transition-colors"
                  title="Enable Trips in Settings"
                >
                  <Plane className="w-5 h-5" />
                  Trips
                  <Lock className="w-3 h-3 ml-auto shrink-0" />
                </button>
              )}
              {/* Safe area spacer */}
              <div className="h-[env(safe-area-inset-bottom)]" />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
