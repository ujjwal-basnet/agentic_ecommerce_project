const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    const res = await fetch(`${API}/chat/stream`, { method: "POST", body });
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
          } catch {}
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
  const res = await fetch(`${API}/api/cart?session_id=${sessionId}`);
  return res.json();
}

export async function addToCartDirect(sessionId: string, productName: string, price: number, qty = 1) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("product_name", productName);
  body.append("price", String(price));
  body.append("quantity", String(qty));
  const res = await fetch(`${API}/api/cart/add`, { method: "POST", body });
  return res.json();
}

export async function updateCartDirect(sessionId: string, productName: string, quantity: number) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("product_name", productName);
  body.append("quantity", String(quantity));
  const res = await fetch(`${API}/api/cart/update`, { method: "POST", body });
  return res.json();
}

export async function removeCartDirect(sessionId: string, productName: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("product_name", productName);
  const res = await fetch(`${API}/api/cart/remove`, { method: "POST", body });
  return res.json();
}

export async function clearChat(sessionId: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  await fetch(`${API}/clear-chat`, { method: "POST", body });
}

export async function uploadPhoto(sessionId: string, file: File) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("photo", file);
  const res = await fetch(`${API}/upload-photo`, { method: "POST", body });
  return res.json();
}

export async function checkout(sessionId: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  const res = await fetch(`${API}/api/checkout`, { method: "POST", body });
  return res.json();
}

export async function fetchOrders(sessionId: string) {
  const res = await fetch(`${API}/api/orders?session_id=${sessionId}`);
  return res.json();
}

export async function tryOnProduct(productId: number, photo: File): Promise<any> {
  const body = new FormData();
  body.append("product_id", String(productId));
  body.append("photo", photo);
  const res = await fetch(`${API}/specialist/tryon`, { method: "POST", body });
  return res.json();
}

export function imageUrl(path: string) {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  return `${API}/${path.replace(/^\//, "")}`;
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
  const res = await fetch(`${API}/api/auth/login`, { method: "POST", body });
  if (!res.ok) throw new Error((await res.text()) || "login failed");
  return res.json();
}

export async function fetchMe(sessionId: string): Promise<{ user: MeUser | null }> {
  const res = await fetch(`${API}/api/auth/me?session_id=${sessionId}`);
  return res.json();
}

export async function logout(sessionId: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  await fetch(`${API}/api/auth/logout`, { method: "POST", body });
}

export function trackView(sessionId: string, productId: number, searchQuery?: string) {
  const body = new FormData();
  body.append("session_id", sessionId);
  body.append("product_id", String(productId));
  if (searchQuery) body.append("search_query", searchQuery);
  // Fire-and-forget; never block product rendering on tracking.
  fetch(`${API}/api/track/view`, { method: "POST", body, keepalive: true }).catch(() => {});
}
