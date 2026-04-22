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
}

export function TransactionFilters({
  search,
  onSearchChange,
  category,
  onCategoryChange,
  categories,
}: TransactionFiltersProps) {
  const hasFilters = search || category !== 'all';

  return (
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
          }}
        >
          <X className="w-4 h-4" />
        </Button>
      )}
    </div>
  );
}
