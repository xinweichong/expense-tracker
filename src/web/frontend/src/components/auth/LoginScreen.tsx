import { useState } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { CasheLogo } from '@/components/ui/CasheLogo';
import { motion } from 'framer-motion';
import { fadeUpVariants } from '@/lib/animations';

export function LoginScreen() {
  const { login } = useAuth();
  const [password, setPassword] = useState('');
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(false);
    const ok = await login(password);
    if (!ok) setError(true);
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      {/* Subtle accent glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] rounded-full bg-accent/5 blur-3xl" />
      </div>

      <motion.div
        className="relative w-full max-w-sm space-y-8"
        variants={fadeUpVariants}
        initial="initial"
        animate="animate"
      >
        {/* Branding */}
        <div className="flex flex-col items-center gap-4">
          <CasheLogo size={56} />
          <div className="text-center">
            <h1 className="text-4xl font-bold tracking-tight text-foreground">Cashe</h1>
            <p className="text-muted text-sm mt-2">Know where every dollar goes.</p>
          </div>
        </div>

        {/* Form card */}
        <Card className="p-6">
          <div className="mb-5">
            <p className="text-sm font-semibold text-foreground">Welcome back</p>
            <p className="text-xs text-muted mt-0.5">Enter your password to continue</p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-3">
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-background border-border"
              autoFocus
            />
            {error && (
              <p className="text-sm text-destructive">Incorrect password. Try again.</p>
            )}
            <Button
              type="submit"
              className="w-full"
              disabled={loading || !password}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>
        </Card>
      </motion.div>
    </div>
  );
}
