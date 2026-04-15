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
            onEvent(JSON.parse(raw));
          } catch {}
        }
      }
    }
    onDone();
  } catch (e: any) {
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
