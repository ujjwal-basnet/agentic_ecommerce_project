"use client";

import { useEffect, useState } from "react";
import { login, fetchMe, MeUser } from "@/lib/api";

const STORAGE_KEY = "smartshop_user";

function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = localStorage.getItem("smartshop_session");
  if (!sid) {
    sid = (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)) as string;
    localStorage.setItem("smartshop_session", sid);
  }
  return sid;
}

export function LoginGate({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MeUser | null>(null);
  const [checking, setChecking] = useState(true);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const sid = getSessionId();
    const cached = localStorage.getItem(STORAGE_KEY);
    if (cached) {
      try {
        const parsed = JSON.parse(cached) as MeUser;
        setUser(parsed);
      } catch {}
    }
    fetchMe(sid)
      .then((res) => {
        if (res.user) {
          setUser(res.user);
          localStorage.setItem(STORAGE_KEY, JSON.stringify(res.user));
        }
      })
      .finally(() => setChecking(false));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setErr(null);
    setSubmitting(true);
    try {
      const sid = getSessionId();
      const res = await login(sid, name.trim(), email.trim());
      setUser(res.user);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(res.user));
    } catch (e: any) {
      setErr(e.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <span className="font-label text-xs uppercase tracking-widest text-on-surface-variant">Loading…</span>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface p-4">
        <div className="w-full max-w-md bg-surface-container-lowest rounded-2xl p-10 shadow-[0_12px_40px_0_rgba(43,52,55,0.06)]">
          <h1 className="font-headline text-3xl font-light tracking-tight text-on-background">Welcome</h1>
          <p className="font-body text-sm text-on-surface-variant mt-2 leading-relaxed">
            Tell us who you are — we use this to personalize your shopping and keep your order history.
          </p>
          <form onSubmit={onSubmit} className="mt-8 space-y-4">
            <div>
              <label className="block text-[10px] font-label uppercase tracking-widest text-on-surface-variant mb-2">Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-surface-container-low rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/20 font-body"
                placeholder="Elena Alvez"
              />
            </div>
            <div>
              <label className="block text-[10px] font-label uppercase tracking-widest text-on-surface-variant mb-2">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-surface-container-low rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-primary/20 font-body"
                placeholder="elena@example.com"
              />
            </div>
            {err ? (
              <p className="text-xs font-label text-on-error-container bg-error-container/20 rounded-lg px-3 py-2">{err}</p>
            ) : null}
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-primary text-on-primary py-3 rounded-xl font-label text-sm font-medium hover:bg-primary-dim transition-all duration-200 disabled:opacity-60"
            >
              {submitting ? "Signing in…" : "Enter SmartShop"}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export function getStoredUser(): MeUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearStoredUser() {
  if (typeof window !== "undefined") localStorage.removeItem(STORAGE_KEY);
}
