const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function imageUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const clean = path.replace(/^\/+/, "");
  return `${API}/${clean}`;
}

export async function fetchAnalytics(days = 30) {
  const res = await fetch(`${API}/owner/analytics?days=${days}`);
  return res.json();
}

export async function fetchProducts() {
  const res = await fetch(`${API}/owner/products`);
  return res.json();
}

export async function addProduct(form: FormData) {
  const res = await fetch(`${API}/owner/products/new`, { method: "POST", body: form });
  return res.json();
}

export async function deleteProduct(productId: number) {
  const body = new FormData();
  body.append("product_id", String(productId));
  const res = await fetch(`${API}/owner/products/delete`, { method: "POST", body });
  return res.json();
}

export async function postToFacebook(image: File, caption: string) {
  const body = new FormData();
  body.append("image", image);
  body.append("caption", caption);
  const res = await fetch(`${API}/owner/facebook/post`, { method: "POST", body });
  return res.json();
}
