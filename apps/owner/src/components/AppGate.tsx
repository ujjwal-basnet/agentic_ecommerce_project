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
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a]">
        <span className="text-xs uppercase tracking-widest text-neutral-500">Loading…</span>
      </div>
    );
  }

  if (needsLogin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] p-4">
        <div className="w-full max-w-sm bg-[#111] rounded-2xl p-10 border border-neutral-800/50">
          <h1 className="text-2xl font-light tracking-tight text-white">
            SmartShop Owner
          </h1>
          <p className="text-sm text-neutral-500 mt-2 leading-relaxed">
            Enter your credentials to access the dashboard.
          </p>
          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label className="block text-[10px] uppercase tracking-widest text-neutral-500 mb-2">
                Username
              </label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-[#1a1a1a] rounded-xl px-4 py-3 text-sm text-white outline-none focus:ring-2 focus:ring-white/10 border border-neutral-800/50"
                autoComplete="username"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-widest text-neutral-500 mb-2">
                Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-[#1a1a1a] rounded-xl px-4 py-3 text-sm text-white outline-none focus:ring-2 focus:ring-white/10 border border-neutral-800/50"
                autoComplete="current-password"
              />
            </div>
            {err && (
              <p className="text-xs text-red-400 bg-red-900/20 rounded-lg px-3 py-2">
                {err}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-white text-black py-3 rounded-xl text-sm font-medium hover:bg-neutral-200 transition-all duration-200 disabled:opacity-60"
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
