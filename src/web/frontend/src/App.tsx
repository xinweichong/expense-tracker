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
import { TripsPage } from '@/pages/TripsPage';
import { OnboardingPage } from '@/pages/OnboardingPage';
import { AdminPage } from '@/pages/AdminPage';
import { api } from '@/api/client';
import { setCategoryColors } from '@/lib/utils';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: false,
    },
  },
});

function CategoryColorLoader() {
  const { data: categories } = useQuery({
    queryKey: ['categories'],
    queryFn: () => api.getCategories(),
  });
  useEffect(() => {
    if (categories) setCategoryColors(categories);
  }, [categories]);
  return null;
}

function AppContent() {
  const { isAuthenticated, loading } = useAuth();
  const { data: currentUser, isLoading: userLoading } = useCurrentUser();

  if (loading || (isAuthenticated && userLoading)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-muted">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) return <LoginScreen />;

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
        {/* Admin routes — no AppShell chrome */}
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/*" element={<AdminPage />} />

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
          <Route path="trips" element={<TripsPage />} />
        </Route>
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
