const TOKEN_KEY = "smartshop_gate_token";

export function getGateToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setGateToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearGateToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function apiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000")
    .replace(/\/+$/, "")
    .replace(/\/api$/i, "");
}

export async function gateLogin(username: string, password: string): Promise<string> {
  const API = apiBase();
  const body = new FormData();
  body.append("username", username);
  body.append("password", password);
  const res = await fetch(`${API}/api/gate/login`, { method: "POST", body });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(data.detail || "Invalid credentials");
  }
  const data = await res.json();
  setGateToken(data.token);
  return data.token;
}

export async function isGateEnabled(): Promise<boolean> {
  const API = apiBase();
  try {
    const res = await fetch(`${API}/api/gate/check`);
    const data = await res.json();
    return data.enabled === true;
  } catch {
    return false;
  }
}

export function authHeaders(): Record<string, string> {
  const token = getGateToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}
