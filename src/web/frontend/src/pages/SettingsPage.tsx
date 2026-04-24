import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useQueryClient, useMutation, useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { Card } from '@/components/ui/card';
import { PageCard } from '@/components/ui/cards';
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
import { api, type Category } from '@/api/client';
import { setCategoryColors, PALETTE, getCategoryColor } from '@/lib/utils';
import { springs, staggerContainerVariants, staggerItemVariants } from '@/lib/animations';
import { Pencil, Trash2, Plus, X } from 'lucide-react';

const ICON_OPTIONS = [
  '🍜', '🚗', '🛒', '📄', '🎬', '📌', '💰', '🏥', '✈️', '🎓',
  '🏠', '💎', '🎮', '📱', '🏋️', '🎨', '🐾', '🎁', '☕', '🍕',
  '👕', '💊', '🔧', '🎵', '📖', '🌺', '⚡', '🎪', '🌊', '🍀',
];

const CAT_TYPES = [
  { value: 'needs',   label: 'Needs'   },
  { value: 'wants',   label: 'Wants'   },
  { value: 'neutral', label: 'Neutral' },
] as const;

export function SettingsPage() {
  const { data: categories } = useCategories();
  const { data: overrides } = useMerchantOverrides();
  const createCat = useCreateCategory();
  const updateCat = useUpdateCategory();
  const deleteCat = useDeleteCategory();

  const { hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    const el = document.getElementById(hash.slice(1));
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [hash]);

  // Populate getCategoryColor overrides when categories load
  useEffect(() => {
    if (categories) setCategoryColors(categories);
  }, [categories]);

  const qc = useQueryClient();
  const deleteOverride = useMutation({
    mutationFn: (merchant: string) => api.deleteMerchantOverride(merchant),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['merchant-overrides'] }),
  });

  const [showAddCategory, setShowAddCategory] = useState(false);
  const [editingCategory, setEditingCategory] = useState<string | null>(null);
  const [newCatName, setNewCatName] = useState('');
  const [newCatKeywords, setNewCatKeywords] = useState('');
  const [newCatIcon, setNewCatIcon] = useState('📌');
  const [newCatColor, setNewCatColor] = useState('');
  const [editKeywords, setEditKeywords] = useState('');
  const [editIcon, setEditIcon] = useState('');
  const [editColor, setEditColor] = useState('');
  const [error, setError] = useState('');

  // Alert threshold state
  const [anomalyMultiplier, setAnomalyMultiplier] = useState<string>('');
  const [velocityThreshold, setVelocityThreshold] = useState<string>('');

  const { data: settings, refetch: refetchSettings } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.getSettings(),
  });

  useEffect(() => {
    if (settings) {
      setAnomalyMultiplier(String(settings.anomaly_multiplier));
      setVelocityThreshold(String(settings.velocity_alert_threshold));
    }
  }, [settings]);

  const saveSettings = async () => {
    try {
      setError('');
      await api.updateSettings({
        anomaly_multiplier: parseFloat(anomalyMultiplier),
        velocity_alert_threshold: parseInt(velocityThreshold),
      });
      refetchSettings();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to save settings';
      setError(msg);
    }
  };

  const toggleBudgets = async (enabled: boolean) => {
    await api.updateSettings({ budgets_enabled: enabled });
    refetchSettings();
  };

  const toggleGoals = async (enabled: boolean) => {
    await api.updateSettings({ goals_enabled: enabled });
    refetchSettings();
  };

  const toggleTrips = async (enabled: boolean) => {
    await api.updateSettings({ trips_enabled: enabled });
    refetchSettings();
  };

  // Colors already in use by other categories
  const usedColors = (categories ?? [])
    .filter((c: Category) => c.color)
    .map((c: Category) => c.color!.toLowerCase());

  const startEdit = (cat: Category) => {
    setEditingCategory(cat.name);
    setEditKeywords(cat.keywords ?? '');
    setEditIcon(cat.icon ?? '📌');
    setEditColor(cat.color ?? '');
    setError('');
  };

  const handleAddCategory = () => {
    if (!newCatName.trim()) return;
    setError('');
    createCat.mutate(
      {
        name: newCatName.trim(),
        keywords: newCatKeywords.trim() || undefined,
        icon: newCatIcon,
        color: newCatColor || undefined,
      },
      {
        onSuccess: () => {
          setShowAddCategory(false);
          setNewCatName('');
          setNewCatKeywords('');
          setNewCatIcon('📌');
          setNewCatColor('');
        },
        onError: (err: Error) => setError(err.message),
      },
    );
  };

  const handleUpdateCategory = (name: string) => {
    setError('');
    updateCat.mutate(
      {
        name,
        data: {
          keywords: editKeywords,
          icon: editIcon,
          color: editColor || undefined,
        },
      },
      {
        onSuccess: () => setEditingCategory(null),
        onError: (err: Error) => setError(err.message),
      },
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
    <div className="p-4 space-y-4 md:h-full md:overflow-hidden md:grid md:gap-4 md:p-6 md:space-y-0 page-grid-settings">

      {/* ── Title area ── */}
      <div className="area-title">
        <h1 className="text-xl font-bold">Settings</h1>
      </div>

      {/* ── Left panel: categories + merchant overrides ── */}
      <div className="area-left grid-scroll-panel space-y-4">

        {/* Categories */}
        <Card className="border-border">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h2 className="font-medium">Categories</h2>
            <Button size="sm" variant="ghost" onClick={() => { setShowAddCategory(true); setError(''); }}>
              <Plus className="w-4 h-4 mr-1" />
              Add
            </Button>
          </div>
          <motion.div
            className="divide-y divide-border"
            variants={staggerContainerVariants}
            initial="initial"
            animate="animate"
          >
            <AnimatePresence>
              {categories?.map((cat: Category) => (
                <motion.div
                  key={cat.name}
                  className="px-4 py-3"
                  variants={staggerItemVariants}
                  exit={{ opacity: 0, transition: { duration: 0.15 } }}
                >
                {editingCategory === cat.name ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      {/* Icon picker */}
                      <div className="shrink-0">
                        <label className="text-xs text-muted block mb-1">Icon</label>
                        <div className="flex flex-wrap gap-1 max-w-[200px]">
                          {ICON_OPTIONS.map((ic) => (
                            <button
                              key={ic}
                              type="button"
                              className={`w-7 h-7 rounded text-sm flex items-center justify-center border transition-colors ${editIcon === ic ? 'border-primary bg-primary/10' : 'border-transparent hover:bg-accent'}`}
                              onClick={() => setEditIcon(ic)}
                            >
                              {ic}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs text-muted">Keywords (comma-separated)</label>
                      <Input
                        value={editKeywords}
                        onChange={(e) => setEditKeywords(e.target.value)}
                        placeholder="keyword1, keyword2"
                        className="bg-background border-border text-sm"
                        autoFocus
                      />
                    </div>
                    <div>
                      <label className="text-xs text-muted">Color</label>
                      <div className="flex flex-wrap gap-2 mt-1">
                        {PALETTE.map((c) => {
                          const taken = usedColors.includes(c.toLowerCase()) && (cat.color?.toLowerCase() !== c.toLowerCase());
                          return (
                            <motion.button
                              key={c}
                              type="button"
                              disabled={taken}
                              title={taken ? 'Already in use' : c}
                              className={`w-7 h-7 rounded-full border-2 transition-colors ${editColor === c ? 'border-white' : 'border-transparent'} ${taken ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}`}
                              style={{ backgroundColor: c }}
                              onClick={() => setEditColor(c)}
                              animate={{ scale: editColor === c ? 1.1 : 1 }}
                              whileHover={taken ? {} : { scale: editColor === c ? 1.1 : 1.05 }}
                              transition={springs.snappy}
                            />
                          );
                        })}
                      </div>
                    </div>
                    {error && <p className="text-xs text-destructive">{error}</p>}
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => handleUpdateCategory(cat.name)} disabled={updateCat.isPending}>
                        Save
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => { setEditingCategory(null); setError(''); }}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className="inline-block w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: cat.color || getCategoryColor(cat.name) }}
                        />
                        <span className="text-lg">{cat.icon || '📌'}</span>
                        <span className="text-sm font-medium">{cat.name}</span>
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => startEdit(cat)}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive"
                          onClick={() => handleDeleteCategory(cat.name)}
                          disabled={deleteCat.isPending}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                    {/* Type selector — immediate save */}
                    <div className="flex items-center gap-2 mt-1.5 ml-7">
                      <label className="text-xs text-muted">Type</label>
                      <select
                        value={cat.type ?? 'neutral'}
                        onChange={async (e) => {
                          await api.updateCategory(cat.name, {
                            type: e.target.value as 'needs' | 'wants' | 'neutral',
                          });
                          qc.invalidateQueries({ queryKey: ['categories'] });
                        }}
                        className="select-field text-xs py-0.5 h-7"
                      >
                        {CAT_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                      </select>
                    </div>
                    {cat.keywords?.trim() && (
                      <div className="flex flex-wrap gap-1 mt-1.5 ml-7">
                        {cat.keywords.split(',').map((kw) => (
                          <Badge key={kw.trim()} variant="outline" className="text-xs border-border">
                            {kw.trim()}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </>
                )}
                </motion.div>
              ))}
            </AnimatePresence>
            {(!categories || categories.length === 0) && (
              <div className="p-6 text-center text-muted text-sm">No categories yet</div>
            )}
          </motion.div>
        </Card>

        {/* Merchant Overrides */}
        <Card className="border-border">
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
                  className="h-7 w-7 text-destructive"
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

      {/* ── Right panel: feature toggles + alert thresholds ── */}
      <div className="area-right grid-scroll-panel space-y-4">

        {/* Feature Toggles */}
        <div id="feature-toggles">
          <PageCard title="Feature Toggles">
            <div className="divide-y divide-border">
              <div className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-medium text-foreground">Budgets</p>
                  <p className="text-xs text-muted">Set spending limits and track progress</p>
                </div>
                <button
                  onClick={() => toggleBudgets(!settings?.budgets_enabled)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${
                    settings?.budgets_enabled ? 'bg-success' : 'bg-foreground/20'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                      settings?.budgets_enabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-medium text-foreground">Goals</p>
                  <p className="text-xs text-muted">Track savings targets and monthly progress</p>
                </div>
                <button
                  onClick={() => toggleGoals(!settings?.goals_enabled)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${
                    settings?.goals_enabled ? 'bg-success' : 'bg-foreground/20'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                      settings?.goals_enabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
              <div className="flex items-center justify-between py-4">
                <div>
                  <p className="text-sm font-medium text-foreground">Trips</p>
                  <p className="text-xs text-muted">Group transactions by trip and track travel spend</p>
                </div>
                <button
                  onClick={() => toggleTrips(!settings?.trips_enabled)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${
                    settings?.trips_enabled ? 'bg-success' : 'bg-foreground/20'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                      settings?.trips_enabled ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>
          </PageCard>
        </div>

        {/* Alert Thresholds */}
        <PageCard title="Alert Thresholds">
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground">Anomaly Detection Multiplier</label>
              <p className="text-xs text-muted mb-1">Flag transactions exceeding Nx the category average (1.0–10.0)</p>
              <input
                type="number" step="0.1" min="1.0" max="10.0"
                value={anomalyMultiplier}
                onChange={(e) => setAnomalyMultiplier(e.target.value)}
                className="input-field w-32"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Velocity Alert Threshold (%)</label>
              <p className="text-xs text-muted mb-1">Alert when monthly pace exceeds X% of last month (50–300)</p>
              <input
                type="number" step="1" min="50" max="300"
                value={velocityThreshold}
                onChange={(e) => setVelocityThreshold(e.target.value)}
                className="input-field w-32"
              />
            </div>
            <button
              onClick={saveSettings}
              className="btn-action"
            >
              Save
            </button>
            {error && <p className="text-sm text-destructive mt-1">{error}</p>}
          </div>
        </PageCard>

      </div>

      {/* Add Category Dialog — Radix portal, layout-position-independent */}
      <Dialog
        open={showAddCategory}
        onOpenChange={(open) => {
          setShowAddCategory(open);
          if (!open) {
            setNewCatName('');
            setNewCatKeywords('');
            setNewCatIcon('📌');
            setNewCatColor('');
            setError('');
          }
        }}
      >
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
              <label className="text-xs text-muted">Icon</label>
              <div className="flex flex-wrap gap-1 mt-1">
                {ICON_OPTIONS.map((ic) => (
                  <button
                    key={ic}
                    type="button"
                    className={`w-7 h-7 rounded text-sm flex items-center justify-center border transition-colors ${newCatIcon === ic ? 'border-primary bg-primary/10' : 'border-transparent hover:bg-accent'}`}
                    onClick={() => setNewCatIcon(ic)}
                  >
                    {ic}
                  </button>
                ))}
              </div>
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
            <div>
              <label className="text-xs text-muted">Color</label>
              <div className="flex flex-wrap gap-2 mt-1">
                {PALETTE.map((c) => {
                  const taken = usedColors.includes(c.toLowerCase());
                  return (
                    <motion.button
                      key={c}
                      type="button"
                      disabled={taken}
                      title={taken ? 'Already in use' : c}
                      className={`w-7 h-7 rounded-full border-2 transition-colors ${newCatColor === c ? 'border-white' : 'border-transparent'} ${taken ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}`}
                      style={{ backgroundColor: c }}
                      onClick={() => setNewCatColor(c)}
                      animate={{ scale: newCatColor === c ? 1.1 : 1 }}
                      whileHover={taken ? {} : { scale: newCatColor === c ? 1.1 : 1.05 }}
                      transition={springs.snappy}
                    />
                  );
                })}
              </div>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
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

    </div>
  );
}
