import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import { AuthProvider, useAuth } from '@/hooks/useAuth';
import { useCurrentUser } from '@/hooks/useCurrentUser';
import { LoginScreen } from '@/components/auth/LoginScreen';
import { AppShell } from '@/components/layout/AppShell';
import { OverviewPage } from '@/pages/OverviewPage';
import { TransactionsPage } from '@/pages/TransactionsPage';
import { AnalyticsPage } from '@/pages/AnalyticsPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { MerchantsPage } from '@/pages/MerchantsPage';
import { FinancePage } from '@/pages/FinancePage';
import { OnboardingPage } from '@/pages/OnboardingPage';
import { AdminPage } from '@/pages/AdminPage';
import { SetPasswordPage } from '@/pages/SetPasswordPage';
import { api } from '@/api/client';
import { setCategoryColors, nearestSpectrum } from '@/lib/utils';
import { CasheWordmark, B1_WASH } from '@/components/ui/Brand';
import { SPECTRUM_PALETTE } from '@/lib/chartTheme';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: false,
    },
  },
});

async function snapCategoryColorsIfNeeded(
  categories: { name: string; color: string | null }[]
) {
  try {
    const settingsRes = await fetch('/api/settings');
    if (!settingsRes.ok) return;
    const settings = await settingsRes.json();
    if (settings.category_colors_snapped_v2 === 'true') return;

    // Backup current colors before snapping
    await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category_colors_pre_v2: JSON.stringify(
          categories.reduce((acc, c) => ({ ...acc, [c.name]: c.color }), {} as Record<string, string | null>)
        ),
      }),
    });

    // Snap each non-spectrum custom color to its nearest spectrum match
    for (const cat of categories) {
      if (!cat.color) continue;
      if (SPECTRUM_PALETTE.includes(cat.color)) continue;
      const snapped = nearestSpectrum(cat.color);
      await fetch(`/api/categories/${encodeURIComponent(cat.name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ color: snapped }),
      });
    }

    // Mark as done so this never runs again
    await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category_colors_snapped_v2: 'true' }),
    });
  } catch (err) {
    console.warn('[cashe] color snap migration failed:', err);
  }
}

function CategoryColorLoader() {
  const { data: categories } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.getCategories(),
  });
  useEffect(() => {
    if (categories) {
      setCategoryColors(categories);
      // Fire-and-forget: non-fatal, only runs once
      void snapCategoryColorsIfNeeded(categories);
    }
  }, [categories]);
  return null;
}

function AppContent() {
  const { isAuthenticated, loading } = useAuth();
  const { data: currentUser, isLoading: userLoading } = useCurrentUser();

  if (loading || (isAuthenticated && userLoading)) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-6" style={{ background: B1_WASH }}>
        <CasheWordmark size={42} />
        <span className="text-xs text-muted font-mono uppercase tracking-[0.22em]">
          Catching up…
        </span>
      </div>
    );
  }

  if (!isAuthenticated) return <LoginScreen />;

  // Forced password change gate (before onboarding)
  if (currentUser?.force_password_change) return <SetPasswordPage />;

  // Redirect to onboarding if not yet complete (and not already there)
  if (currentUser && !currentUser.onboarding_complete) {
    return (
      <Routes>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="*" element={<Navigate to="/onboarding" replace />} />
      </Routes>
    );
  }

  return (
    <>
      <CategoryColorLoader />
      <Routes>
        {/* Dashboard routes */}
        <Route element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="transactions" element={<TransactionsPage />} />
          <Route path="transactions/:transactionId" element={<TransactionsPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="merchants" element={<MerchantsPage />} />
          <Route path="merchants/:merchantName" element={<MerchantsPage />} />
          <Route path="finance" element={<FinancePage />} />
          <Route path="trips" element={<Navigate to="/finance" replace />} />
        </Route>
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Admin routes bypass the regular user auth flow entirely */}
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/admin/*" element={<AdminPage />} />
          <Route
            path="*"
            element={
              <AuthProvider>
                <AppContent />
              </AuthProvider>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
