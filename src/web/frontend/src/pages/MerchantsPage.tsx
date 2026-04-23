import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api, type MerchantSummary } from '@/api/client';
import { Card, CardContent } from '@/components/ui/card';
import { MerchantProfile } from '@/components/merchants/MerchantProfile';
import { Search } from 'lucide-react';

const SORT_OPTIONS = [
  { value: 'total_spent',       label: 'Total Spent' },
  { value: 'transaction_count', label: 'Transactions' },
  { value: 'last_seen',         label: 'Last Seen' },
  { value: 'merchant_name',     label: 'Name' },
];

const ALL_TAGS = ['online', 'subscription', 'local', 'foreign', 'business', 'cash-equivalent'];

const TAG_COLORS: Record<string, string> = {
  online:           'bg-blue-500/20 text-blue-400',
  subscription:     'bg-purple-500/20 text-purple-400',
  local:            'bg-green-500/20 text-green-400',
  foreign:          'bg-orange-500/20 text-orange-400',
  business:         'bg-indigo-500/20 text-indigo-400',
  'cash-equivalent':'bg-zinc-500/20 text-zinc-400',
};

function formatSGD(v: number) {
  return `$${v.toLocaleString('en-SG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function MerchantsPage() {
  const { merchantName } = useParams<{ merchantName?: string }>();
  const navigate = useNavigate();

  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('total_spent');
  const [tagFilter, setTagFilter] = useState('');
  const [selectedMerchant, setSelectedMerchant] = useState<string | null>(merchantName ?? null);

  // Sync URL param → panel
  useEffect(() => {
    if (merchantName) setSelectedMerchant(merchantName);
  }, [merchantName]);

  const { data: merchants = [], isLoading } = useQuery({
    queryKey: ['merchant-intelligence', sortBy, tagFilter, search],
    queryFn: () =>
      api.getMerchantIntelligenceList({
        sort_by: sortBy as 'total_spent' | 'transaction_count' | 'last_seen' | 'merchant_name',
        tag: tagFilter || undefined,
        search: search || undefined,
        limit: 100,
      }),
    staleTime: 30_000,
  });

  const handleRowClick = (m: MerchantSummary) => {
    setSelectedMerchant(m.merchant);
    navigate(`/merchants/${encodeURIComponent(m.merchant)}`);
  };

  const handleCloseProfile = () => {
    setSelectedMerchant(null);
    navigate('/merchants');
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Merchant list */}
      <div
        className={`flex-1 overflow-y-auto p-4 md:p-6 space-y-4 ${
          selectedMerchant ? 'hidden md:block' : ''
        }`}
      >
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-foreground">Merchants</h1>
          <span className="text-sm text-muted">{merchants.length} merchants</span>
        </div>

        {/* Filters */}
        <div className="space-y-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search merchants…"
              className="w-full pl-9 pr-3 py-2 text-sm bg-background border border-border rounded-md text-foreground placeholder:text-muted"
            />
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="select-field text-xs"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            {ALL_TAGS.map((tag) => (
              <button
                key={tag}
                onClick={() => setTagFilter(tagFilter === tag ? '' : tag)}
                className={`px-2 py-1 text-xs rounded-full border transition-colors ${
                  tagFilter === tag
                    ? `${TAG_COLORS[tag]} border-current`
                    : 'border-border text-muted hover:text-foreground'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>

        {/* Merchants table — Tier 3 bespoke card (bare Card + CardContent p-0) intentional:
             table headers/rows own their px-4 spacing and render edge-to-edge, consistent with
             TransactionsPage which also uses a bare <Card className="overflow-hidden">.
             Do NOT wrap in PageCard — its mandatory p-4 CardContent padding would break the layout. */}
        {isLoading ? (
          <div className="text-muted text-sm py-8 text-center">Loading merchants…</div>
        ) : merchants.length === 0 ? (
          <div className="text-muted text-sm py-8 text-center">No merchants found.</div>
        ) : (
          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted">
                    <th className="text-left px-4 py-3 font-medium">Merchant</th>
                    <th className="text-left px-4 py-3 font-medium hidden sm:table-cell">Category</th>
                    <th className="text-left px-4 py-3 font-medium hidden md:table-cell">Tags</th>
                    <th className="text-right px-4 py-3 font-medium">Total</th>
                    <th className="text-right px-4 py-3 font-medium hidden sm:table-cell">Txns</th>
                    <th className="text-right px-4 py-3 font-medium hidden lg:table-cell">Last Seen</th>
                  </tr>
                </thead>
                <tbody>
                  {merchants.map((m) => (
                    <tr
                      key={m.merchant}
                      onClick={() => handleRowClick(m)}
                      className={`border-b border-border cursor-pointer hover:bg-foreground/5 transition-colors last:border-b-0 ${
                        selectedMerchant === m.merchant ? 'bg-foreground/10' : ''
                      }`}
                    >
                      <td className="px-4 py-3 font-medium text-foreground">{m.merchant}</td>
                      <td className="px-4 py-3 text-muted hidden sm:table-cell">
                        {m.category ?? '—'}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell">
                        <div className="flex flex-wrap gap-1">
                          {(m.tags ?? []).map((tag) => (
                            <span
                              key={tag}
                              className={`px-1.5 py-0.5 text-xs rounded-full ${TAG_COLORS[tag] ?? 'bg-zinc-500/20 text-zinc-400'}`}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-foreground">
                        {formatSGD(m.total_sgd)}
                      </td>
                      <td className="px-4 py-3 text-right text-muted hidden sm:table-cell">
                        {m.transaction_count}
                      </td>
                      <td className="px-4 py-3 text-right text-muted hidden lg:table-cell">
                        {m.last_seen ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Profile panel — slide-over on desktop, full-screen on mobile */}
      {selectedMerchant && (
        <div className="w-full md:w-96 border-l border-border bg-card flex-shrink-0 overflow-hidden">
          <MerchantProfile
            merchant={selectedMerchant}
            onClose={handleCloseProfile}
          />
        </div>
      )}
    </div>
  );
}
