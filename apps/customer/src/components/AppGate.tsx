"use client";

import { useEffect, useState } from "react";
import { getGateToken, gateLogin, isGateEnabled } from "@/lib/gate";

export function AppGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [needsLogin, setNeedsLogin] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const enabled = await isGateEnabled();
      if (!enabled) {
        setReady(true);
        return;
      }
      const token = getGateToken();
      if (token) {
        setReady(true);
      } else {
        setNeedsLogin(true);
      }
    })();
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setErr(null);
    setSubmitting(true);
    try {
      await gateLogin(username.trim(), password);
      setNeedsLogin(false);
      setReady(true);
    } catch (e: any) {
      setErr(e.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready && !needsLogin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <span className="font-label text-xs uppercase tracking-widest text-on-surface-variant">
          Loading…
        </span>
      </div>
    );
  }

  if (needsLogin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface p-4">
        <div className="w-full max-w-sm bg-surface-container-lowest rounded-2xl p-10 shadow-[0_12px_40px_0_rgba(43,52,55,0.06)]">
          <h1 className="font-headline text-2xl font-light tracking-tight text-on-background">
            SmartShop Access
          </h1>
          <p className="font-body text-sm text-on-surface-variant mt-2 leading-relaxed">
            Enter your credentials to continue.
          </p>
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label className="block text-[10px] font-label uppercase tracking-widest text-on-surface-variant mb-2">
                Username
              </label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-surface-container-low rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/20 font-body"
                autoComplete="username"
              />
            </div>
            <div>
              <label className="block text-[10px] font-label uppercase tracking-widest text-on-surface-variant mb-2">
                Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-surface-container-low rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/20 font-body"
                autoComplete="current-password"
              />
            </div>
            {err && (
              <p className="text-xs font-label text-on-error-container bg-error-container/20 rounded-lg px-3 py-2">
                {err}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-primary text-on-primary py-3 rounded-xl font-label text-sm font-medium hover:bg-primary-dim transition-all duration-200 disabled:opacity-60"
            >
              {submitting ? "Verifying…" : "Continue"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
