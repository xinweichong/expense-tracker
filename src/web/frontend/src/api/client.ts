const BASE = '';

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...opts?.headers,
    },
  });
  if (res.status === 401) {
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error: ${res.status} ${body}`);
  }
  return res.json();
}

export interface Transaction {
  id: number;
  source: string;
  source_id: string;
  amount: number;
  currency: string;
  exchange_rate: number;
  merchant: string | null;
  description: string | null;
  category: string | null;
  transaction_date: string;
  ingested_at: string;
  type: string;
}

export interface Category {
  name: string;
  keywords: string | null;
  icon: string | null;
  color: string | null;
}

export interface MerchantSummary {
  merchant: string;
  total_sgd: number;
  transaction_count: number;
  avg_amount_sgd: number;
  category: string | null;
  first_seen: string;
  last_seen: string;
  tags: string[];
  notes: string;
}

export interface MerchantProfile extends MerchantSummary {}

export interface MerchantTrend {
  merchant: string;
  months: Array<{ month: string; total: number; count: number }>;
  current_month: number;
  previous_month: number;
  trend: 'up' | 'down' | 'stable';
}

export const api = {
  // Auth
  login: (password: string) =>
    request<{ status: string }>('/api/login', {
      method: 'POST',
      body: JSON.stringify({ password }),
    }),

  // Transactions
  getTransactions: (params?: Record<string, string | number>) => {
    const query = params
      ? '?' + new URLSearchParams(
          Object.entries(params).map(([k, v]) => [k, String(v)])
        ).toString()
      : '';
    return request<Transaction[]>(`/api/transactions${query}`);
  },

  getTransaction: (id: number) =>
    request<Transaction>(`/api/transactions/${id}`),

  createTransaction: (data: Partial<Transaction> & { source?: string }) =>
    request<Transaction>('/api/transactions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateTransaction: (id: number, data: Partial<Transaction>) =>
    request<Transaction>(`/api/transactions/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteTransaction: (id: number) =>
    request<{ status: string }>(`/api/transactions/${id}`, { method: 'DELETE' }),

  // Summary & Analytics
  getSummary: (start_date: string, end_date: string) =>
    request<any>(`/api/summary?start_date=${start_date}&end_date=${end_date}`),

  getTrend: (start_date: string, end_date: string) =>
    request<any>(`/api/trend?start_date=${start_date}&end_date=${end_date}`),

  getTrendByCategory: (start_date: string, end_date: string) =>
    request<any>(`/api/trend/by-category?start_date=${start_date}&end_date=${end_date}`),

  getBalance: (start_date: string, end_date: string) =>
    request<any>(`/api/balance?start_date=${start_date}&end_date=${end_date}`),

  getInsights: (start_date: string, end_date: string) =>
    request<any>(`/api/insights?start_date=${start_date}&end_date=${end_date}`),

  getMerchants: (start_date: string, end_date: string) =>
    request<string[]>(`/api/merchants?start_date=${start_date}&end_date=${end_date}`),

  getRecurring: () =>
    request<any[]>('/api/recurring'),

  getIncomeVsExpense: (months = 6) =>
    request<Array<{ month: string; income: number; expenses: number }>>(
      `/api/income-vs-expense?months=${months}`
    ),

  // Categories
  getCategories: () =>
    request<Category[]>('/api/categories'),

  createCategory: (data: { name: string; keywords?: string; icon?: string; color?: string }) =>
    request<{ status: string; name: string }>('/api/categories', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateCategory: (name: string, data: { keywords?: string; icon?: string; color?: string }) =>
    request<{ status: string; name: string }>(`/api/categories/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteCategory: (name: string) =>
    request<{ status: string; reassigned: number }>(`/api/categories/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),

  // Merchant Overrides
  getMerchantOverrides: () =>
    request<{ merchant: string; category: string }[]>('/api/merchant-overrides'),

  deleteMerchantOverride: (merchant: string) =>
    request<{ status: string }>(`/api/merchant-overrides/${encodeURIComponent(merchant)}`, {
      method: 'DELETE',
    }),

  // Apple Wallet
  getAppleWalletCards: () =>
    request<string[]>('/api/apple-wallet/cards'),

  // Analytics endpoints
  getAnalyticsComparison: (period: string, date?: string) => {
    const params = new URLSearchParams({ period });
    if (date) params.set('date', date);
    return request<any>(`/api/analytics/comparison?${params}`);
  },

  getAnalyticsMerchants: (limit = 10, merchant?: string) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (merchant) params.set('merchant', merchant);
    return request<any>(`/api/analytics/merchants?${params}`);
  },

  getAnalyticsVelocity: () =>
    request<any>('/api/analytics/velocity'),

  getAnalyticsAlerts: () =>
    request<any>('/api/analytics/alerts'),

  getAnalyticsSummaries: () =>
    request<any>('/api/analytics/summaries'),

  // Merchant Intelligence
  getMerchantIntelligenceList: (params?: {
    sort_by?: string;
    tag?: string;
    category?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = params
      ? '?' + new URLSearchParams(
          Object.entries(params)
            .filter(([, v]) => v !== undefined && v !== '')
            .map(([k, v]) => [k, String(v)])
        ).toString()
      : '';
    return request<MerchantSummary[]>(`/api/merchant-intelligence${query}`);
  },

  getMerchantProfile: (merchant: string) =>
    request<MerchantProfile>(`/api/merchant-intelligence/${encodeURIComponent(merchant)}`),

  setMerchantTags: (merchant: string, tags: string[]) =>
    request<{ merchant: string; tags: string[]; notes: string }>(
      `/api/merchant-intelligence/${encodeURIComponent(merchant)}/tags`,
      { method: 'PUT', body: JSON.stringify({ tags }) }
    ),

  setMerchantNotes: (merchant: string, notes: string) =>
    request<{ merchant: string; tags: string[]; notes: string }>(
      `/api/merchant-intelligence/${encodeURIComponent(merchant)}/notes`,
      { method: 'PUT', body: JSON.stringify({ notes }) }
    ),

  getMerchantTrend: (merchant: string) =>
    request<MerchantTrend>(`/api/merchant-intelligence/${encodeURIComponent(merchant)}/trend`),

  // App Settings
  getSettings: () =>
    request<{ anomaly_multiplier: number; velocity_alert_threshold: number }>('/api/settings'),

  updateSettings: (data: { anomaly_multiplier?: number; velocity_alert_threshold?: number }) =>
    request<{ anomaly_multiplier: number; velocity_alert_threshold: number }>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
};
