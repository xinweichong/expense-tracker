const BASE = '';

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...opts?.headers,
    },
  });
  if (res.status === 401) throw new Error('Unauthorized');
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

  getBalance: (start_date: string, end_date: string) =>
    request<any>(`/api/balance?start_date=${start_date}&end_date=${end_date}`),

  getInsights: (start_date: string, end_date: string) =>
    request<any>(`/api/insights?start_date=${start_date}&end_date=${end_date}`),

  getMerchants: (start_date: string, end_date: string) =>
    request<string[]>(`/api/merchants?start_date=${start_date}&end_date=${end_date}`),

  getRecurring: () =>
    request<any[]>('/api/recurring'),

  // Categories
  getCategories: () =>
    request<Category[]>('/api/categories'),

  createCategory: (data: { name: string; keywords?: string; icon?: string }) =>
    request<{ status: string; name: string }>('/api/categories', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateCategory: (name: string, data: { keywords?: string }) =>
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
};
