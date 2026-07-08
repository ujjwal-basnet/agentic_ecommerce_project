import { authHeaders, clearGateToken } from "./gate";

function apiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (env) return env.replace(/\/+$/, "").replace(/\/api$/i, "");
  if (typeof window !== "undefined") {
    const { protocol, hostname, port } = window.location;
    if (port === "8000") return `${protocol}//${hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const base = apiBase();
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

async function gatedFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  for (const [k, v] of Object.entries(authHeaders())) headers.set(k, v);
  const res = await fetch(url, { ...init, headers });
  if (res.status === 401) {
    clearGateToken();
    window.location.reload();
  }
  return res;
}

export async function fetchSSE(
  message: string,
  sessionId: string,
  userImagePath: string | null,
  onEvent: (data: any) => void,
  onDone: () => void,
  onError: (err: string) => void,
  interfaceMode: string = "web",
) {
  const body = new FormData();
  body.append("message", message);
  body.append("session_id", sessionId);
  body.append("interface_mode", interfaceMode);
  if (userImagePath) body.append("user_image_path", userImagePath);

  let sawErrorEvent = false;

  try {
    const res = await gatedFetch(apiUrl("/chat/stream"), { method: "POST", body });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const reader = res.body?.getReader();
    if (!reader) throw new Error("No stream");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data:")) {
          const raw = line.slice(5).trim();
          if (!raw) continue;
          try {
            const parsed = JSON.parse(raw);
            if (parsed.type === "error") sawErrorEvent = true;
            onEvent(parsed);
          } catch { }
        }
      }
    }
    onDone();
  } catch (e: any) {
    if (sawErrorEvent) {
      onDone();
      return;
    }
    onError(e.message || "Connection failed");
  }
}

export async function fetchCart(sessionId: string) {
  const res = await gatedFetch(apiUrl(`/api/cart?session_id=${sessionId}`));
  return res.json();
}

export async function addToCartDirect(sessionId: string, productName: string, price: number, qty = 1) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("product_name", productName);
  body.append("price", String(price));
  body.append("quantity", String(qty));
  const res = await gatedFetch(apiUrl("/api/cart/add"), { method: "POST", body });
  return res.json();
}

export async function updateCartDirect(sessionId: string, productName: string, quantity: number) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("product_name", productName);
  body.append("quantity", String(quantity));
  const res = await gatedFetch(apiUrl("/api/cart/update"), { method: "POST", body });
  return res.json();
}

export async function removeCartDirect(sessionId: string, productName: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("product_name", productName);
  const res = await gatedFetch(apiUrl("/api/cart/remove"), { method: "POST", body });
  return res.json();
}

export async function clearChat(sessionId: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  await gatedFetch(apiUrl("/clear-chat"), { method: "POST", body });
}

export async function uploadPhoto(sessionId: string, file: File) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("photo", file);
  const res = await gatedFetch(apiUrl("/upload-photo"), { method: "POST", body });
  return res.json();
}

export async function checkout(sessionId: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  const res = await gatedFetch(apiUrl("/api/checkout"), { method: "POST", body });
  return res.json();
}

export async function fetchOrders(sessionId: string) {
  const res = await gatedFetch(apiUrl(`/api/orders?session_id=${sessionId}`));
  return res.json();
}

export async function tryOnProduct(productId: number, photo: File, model: string = "nano_banana"): Promise<any> {
  const body = new FormData();
  body.append("product_id", String(productId));
  body.append("photo", photo);
  body.append("model", model);
  const res = await gatedFetch(apiUrl("/specialist/tryon"), { method: "POST", body });
  return res.json();
}

export async function fetchImageModels(): Promise<{ models: { id: string; label: string; description: string; supports_edit: boolean }[] }> {
  const res = await gatedFetch(apiUrl("/specialist/image-models"));
  return res.json();
}

export function imageUrl(path: string) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return apiUrl(`/${path.replace(/^\//, "")}`);
}

// ─── Auth + behavior tracking ─────────────────────────────────────────

export interface MeUser {
  id: number;
  name: string;
  email: string;
}

export async function login(sessionId: string, name: string, email: string): Promise<{ ok: boolean; user: MeUser }> {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("name", name);
  body.append("email", email);
  const res = await gatedFetch(apiUrl("/api/auth/login"), { method: "POST", body });
  if (!res.ok) throw new Error((await res.text()) || "login failed");
  return res.json();
}

export async function fetchMe(sessionId: string): Promise<{ user: MeUser | null }> {
  const res = await gatedFetch(apiUrl(`/api/auth/me?session_id=${sessionId}`));
  return res.json();
}

export async function logout(sessionId: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  await gatedFetch(apiUrl("/api/auth/logout"), { method: "POST", body });
}

export async function deleteAccount(sessionId: string): Promise<{ ok: boolean; deleted: boolean }> {
  const body = new FormData();
  body.append("session_id", sessionId);
  const res = await gatedFetch(apiUrl("/api/auth/delete-account"), { method: "POST", body });
  if (!res.ok) throw new Error((await res.text()) || "delete account failed");
  return res.json();
}

export function trackView(sessionId: string, productId: number, searchQuery?: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("product_id", String(productId));
  if (searchQuery) body.append("search_query", searchQuery);
  // Fire-and-forget; never block product rendering on tracking.
  gatedFetch(apiUrl("/api/track/view"), { method: "POST", body, keepalive: true }).catch(() => { });
}
