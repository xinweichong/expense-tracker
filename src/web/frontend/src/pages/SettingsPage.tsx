import { useState } from 'react';
import { useQueryClient, useMutation } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  useCategories,
  useCreateCategory,
  useUpdateCategory,
  useDeleteCategory,
  useMerchantOverrides,
} from '@/hooks/useCategories';
import { api } from '@/api/client';
import { Pencil, Trash2, Plus, X } from 'lucide-react';

export function SettingsPage() {
  const { data: categories } = useCategories();
  const { data: overrides } = useMerchantOverrides();
  const createCat = useCreateCategory();
  const updateCat = useUpdateCategory();
  const deleteCat = useDeleteCategory();

  const qc = useQueryClient();
  const deleteOverride = useMutation({
    mutationFn: (merchant: string) => api.deleteMerchantOverride(merchant),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['merchant-overrides'] }),
  });

  const [showAddCategory, setShowAddCategory] = useState(false);
  const [editingCategory, setEditingCategory] = useState<string | null>(null);
  const [newCatName, setNewCatName] = useState('');
  const [newCatKeywords, setNewCatKeywords] = useState('');
  const [editKeywords, setEditKeywords] = useState('');

  const handleAddCategory = () => {
    if (!newCatName.trim()) return;
    createCat.mutate(
      { name: newCatName.trim(), keywords: newCatKeywords.trim() || undefined },
      {
        onSuccess: () => {
          setShowAddCategory(false);
          setNewCatName('');
          setNewCatKeywords('');
        },
      }
    );
  };

  const handleUpdateKeywords = (name: string) => {
    updateCat.mutate(
      { name, data: { keywords: editKeywords } },
      { onSuccess: () => setEditingCategory(null) }
    );
  };

  const handleDeleteCategory = (name: string) => {
    if (confirm(`Delete category "${name}"? Transactions will be moved to "Other".`)) {
      deleteCat.mutate(name);
    }
  };

  const handleDeleteOverride = (merchant: string) => {
    if (confirm(`Remove learned override for "${merchant}"?`)) {
      deleteOverride.mutate(merchant);
    }
  };

  return (
    <div className="p-4 md:p-6 lg:p-8 max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-bold">Settings</h1>

      {/* Categories */}
      <Card className="bg-card border-border">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="font-medium">Categories</h2>
          <Button size="sm" variant="ghost" onClick={() => setShowAddCategory(true)}>
            <Plus className="w-4 h-4 mr-1" />
            Add
          </Button>
        </div>
        <div className="divide-y divide-border">
          {categories?.map((cat) => (
            <div key={cat.name} className="px-4 py-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">{cat.name}</span>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => {
                      setEditingCategory(cat.name);
                      setEditKeywords(cat.keywords ?? '');
                    }}
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 text-accent"
                    onClick={() => handleDeleteCategory(cat.name)}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
              {cat.keywords && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {cat.keywords.split(',').map((kw) => (
                    <Badge key={kw.trim()} variant="outline" className="text-xs border-border">
                      {kw.trim()}
                    </Badge>
                  ))}
                </div>
              )}
              {editingCategory === cat.name && (
                <div className="mt-2 flex gap-2">
                  <Input
                    value={editKeywords}
                    onChange={(e) => setEditKeywords(e.target.value)}
                    placeholder="keyword1, keyword2"
                    className="bg-background border-border text-sm"
                    autoFocus
                  />
                  <Button size="sm" onClick={() => handleUpdateKeywords(cat.name)} disabled={updateCat.isPending}>
                    Save
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditingCategory(null)}>
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          ))}
          {(!categories || categories.length === 0) && (
            <div className="p-6 text-center text-muted text-sm">No categories yet</div>
          )}
        </div>
      </Card>

      {/* Add Category Dialog */}
      <Dialog open={showAddCategory} onOpenChange={setShowAddCategory}>
        <DialogContent className="bg-card border-border">
          <DialogHeader>
            <DialogTitle>Add Category</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-muted">Name</label>
              <Input
                value={newCatName}
                onChange={(e) => setNewCatName(e.target.value)}
                placeholder="e.g. Healthcare"
                className="bg-background border-border"
                autoFocus
              />
            </div>
            <div>
              <label className="text-xs text-muted">Keywords (comma-separated)</label>
              <Input
                value={newCatKeywords}
                onChange={(e) => setNewCatKeywords(e.target.value)}
                placeholder="e.g. clinic, pharmacy, doctor"
                className="bg-background border-border"
              />
            </div>
            <Separator />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowAddCategory(false)}>
                Cancel
              </Button>
              <Button onClick={handleAddCategory} disabled={!newCatName.trim() || createCat.isPending}>
                Add
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Merchant Overrides */}
      <Card className="bg-card border-border">
        <div className="p-4 border-b border-border">
          <h2 className="font-medium">Learned Merchant Overrides</h2>
          <p className="text-xs text-muted mt-0.5">These are merchant-to-category mappings learned from your recategorizations.</p>
        </div>
        <div className="divide-y divide-border">
          {overrides?.map((ov) => (
            <div key={ov.merchant} className="px-4 py-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{ov.merchant}</p>
                <p className="text-xs text-muted">→ {ov.category}</p>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-accent"
                onClick={() => handleDeleteOverride(ov.merchant)}
                disabled={deleteOverride.isPending}
              >
                <X className="w-3.5 h-3.5" />
              </Button>
            </div>
          ))}
          {(!overrides || overrides.length === 0) && (
            <div className="p-6 text-center text-muted text-sm">
              No learned overrides yet
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
