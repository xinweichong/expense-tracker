import { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Search, X } from 'lucide-react';

interface TransactionFiltersProps {
  search: string;
  onSearchChange: (v: string) => void;
  category: string;
  onCategoryChange: (v: string) => void;
  categories: { name: string }[];
  startDate: string;
  setStartDate: (v: string) => void;
  endDate: string;
  setEndDate: (v: string) => void;
}

export function TransactionFilters({
  search,
  onSearchChange,
  category,
  onCategoryChange,
  categories,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
}: TransactionFiltersProps) {
  const hasFilters = search || category !== 'all' || startDate || endDate;

  const handleExport = () => {
    const params = new URLSearchParams();
    if (search) params.set('merchant', search);
    if (category && category !== 'all') params.set('category', category);
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    window.open(`/api/transactions/export?${params.toString()}`, '_blank');
  };

  const quickSelects = useMemo(() => {
    const today = new Date();
    const todayStr = today.toISOString().slice(0, 10);
    return [
      {
        label: 'Last 30 days',
        start: new Date(today.getFullYear(), today.getMonth(), today.getDate() - 30)
          .toISOString().slice(0, 10),
        end: todayStr,
      },
      {
        label: 'This month',
        start: `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`,
        end: todayStr,
      },
      {
        label: 'Last month',
        start: (() => {
          const d = new Date(today.getFullYear(), today.getMonth() - 1, 1);
          return d.toISOString().slice(0, 10);
        })(),
        end: (() => {
          const d = new Date(today.getFullYear(), today.getMonth(), 0);
          return d.toISOString().slice(0, 10);
        })(),
      },
      { label: 'All time', start: '', end: '' },
    ];
  }, []); // empty deps: computed once per component mount

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <Input
            placeholder="Search merchant or description..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9 bg-background border-border"
          />
        </div>
        <Select value={category} onValueChange={onCategoryChange}>
          <SelectTrigger className="w-full sm:w-40 bg-background border-border">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {categories.map((cat) => (
              <SelectItem key={cat.name} value={cat.name}>
                {cat.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {hasFilters && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              onSearchChange('');
              onCategoryChange('all');
              setStartDate('');
              setEndDate('');
            }}
          >
            <X className="w-4 h-4" />
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <input
          type="date"
          aria-label="Start date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="px-2 py-1.5 text-sm bg-background border border-border rounded-md text-foreground"
        />
        <span className="text-muted text-sm">–</span>
        <input
          type="date"
          aria-label="End date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="px-2 py-1.5 text-sm bg-background border border-border rounded-md text-foreground"
        />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {quickSelects.map((q) => {
          const isActive = q.label !== 'All time' && startDate === q.start && endDate === q.end;
          return (
            <button
              key={q.label}
              type="button"
              onClick={() => { setStartDate(q.start); setEndDate(q.end); }}
              className={`px-2.5 py-1 text-xs rounded-full border transition-colors ${
                isActive
                  ? 'border-foreground text-foreground bg-foreground/10'
                  : 'border-border text-muted hover:text-foreground'
              }`}
            >
              {q.label}
            </button>
          );
        })}
      </div>

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleExport}
          className="px-3 py-1.5 text-xs border border-border rounded-md text-muted hover:text-foreground hover:border-foreground/40 transition-colors"
        >
          Export CSV
        </button>
      </div>
    </div>
  );
}
