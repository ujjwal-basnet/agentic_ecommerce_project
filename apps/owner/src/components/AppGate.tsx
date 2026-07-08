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
      <div className="flex min-h-screen items-center justify-center bg-[#d8ecf5]">
        <span className="text-xs uppercase tracking-[0.24em] text-slate-500">Loading...</span>
      </div>
    );
  }

  if (needsLogin) {
    return (
      <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#d8ecf5] px-4 py-8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(255,255,255,0.95),transparent_28%),radial-gradient(circle_at_88%_8%,rgba(255,255,255,0.9),transparent_26%),linear-gradient(180deg,rgba(190,224,239,0.92),rgba(232,246,250,0.78))]" />
        <div className="relative grid w-full max-w-5xl overflow-hidden rounded-lg bg-white shadow-[0_24px_70px_rgba(44,82,102,0.2)] ring-1 ring-white/70 md:grid-cols-[0.95fr_1.05fr]">
          <section className="relative min-h-[280px] overflow-hidden bg-slate-900 md:min-h-[560px]">
            <img
              src="/smartshop-login-visual.png"
              alt=""
              aria-hidden="true"
              className="absolute inset-0 h-full w-full object-cover"
            />
            <div className="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black/68 via-black/18 to-transparent" />
            <div className="absolute bottom-5 left-5 right-5">
              <p className="max-w-[13rem] text-4xl font-extrabold uppercase leading-[0.92] text-white drop-shadow md:text-5xl">
                Explore. Manage. Grow.
              </p>
            </div>
          </section>

          <section className="flex min-h-[500px] items-center justify-center px-6 py-10 sm:px-10">
            <div className="w-full max-w-sm">
              <div className="mb-8 flex flex-col items-center text-center">
                <div className="mb-3 grid h-10 w-10 place-items-center rounded-full border border-slate-200 bg-white text-sm font-black tracking-tight text-slate-950 shadow-sm">
                  SS
                </div>
                <h1 className="text-3xl font-black uppercase tracking-normal text-slate-950">
                  Welcome Back
                </h1>
                <p className="mt-2 text-xs font-medium text-slate-500">
                  Enter your username and password to access the owner dashboard.
                </p>
              </div>

              <form onSubmit={onSubmit} className="space-y-4">
                <div>
                  <label className="mb-2 block text-[11px] font-semibold text-slate-700">
                    Username
                  </label>
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="h-11 w-full rounded-lg border border-transparent bg-slate-50 px-4 text-sm text-slate-950 outline-none transition focus:border-slate-300 focus:bg-white focus:ring-4 focus:ring-slate-200/70"
                    placeholder="admin"
                    autoComplete="username"
                  />
                </div>
                <div>
                  <label className="mb-2 block text-[11px] font-semibold text-slate-700">
                    Password
                  </label>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-11 w-full rounded-lg border border-transparent bg-slate-50 px-4 text-sm text-slate-950 outline-none transition focus:border-slate-300 focus:bg-white focus:ring-4 focus:ring-slate-200/70"
                    placeholder="Enter password"
                    autoComplete="current-password"
                  />
                </div>
                {err && (
                  <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-red-100">
                    {err}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={submitting}
                  className="h-11 w-full rounded-lg bg-black text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Signing in..." : "Sign in"}
                </button>
              </form>
            </div>
          </section>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
