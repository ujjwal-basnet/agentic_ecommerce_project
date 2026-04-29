import { authHeaders, clearGateToken } from "./gate";

function apiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (env) return env.replace(/\/+$/, "").replace(/\/api$/i, "");
  if (typeof window !== "undefined") {
    const { protocol, hostname, port } = window.location;
    if (port === "8000") return `${protocol}//${hostname}:8000`;
  }
  return "http://localhost:8000";
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

export function imageUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  const clean = path.replace(/^\/+/, "");
  return apiUrl(`/${clean}`);
}

// ─── Inventory ─────────────────────────────────────────────────────────

export async function fetchProducts() {
  const res = await gatedFetch(apiUrl("/owner/products"));
  return res.json();
}

export async function addProduct(form: FormData) {
  const res = await gatedFetch(apiUrl("/owner/products/new"), { method: "POST", body: form });
  return res.json();
}

export async function updateProduct(form: FormData) {
  const res = await gatedFetch(apiUrl("/owner/products/update"), { method: "POST", body: form });
  return res.json();
}

export async function deleteProduct(productId: number) {
  const body = new FormData();
  body.append("product_id", String(productId));
  const res = await gatedFetch(apiUrl("/owner/products/delete"), { method: "POST", body });
  return res.json();
}

export async function postToFacebook(_image: File, _caption: string) {
  return {
    success: false,
    message: "Direct owner Facebook posting is disabled. Use Campaign Launch instead.",
  };
}

// ─── Analytics (Lumière Noir) ─────────────────────────────────────────

export type ForecastRange = "7d" | "30d" | "ytd";

export interface OverviewStats {
  total_revenue: number;
  total_orders: number;
  total_customers: number;
  total_products: number;
  today_revenue: number;
  yesterday_revenue: number;
  day_delta_pct: number;
}

export interface ForecastPoint {
  date: string;
  value: number;
  is_forecast: boolean;
}

export interface TrendingProduct {
  product_id: number;
  name: string;
  price: number;
  image_path: string | null;
  score: number;
  demand_pct: number;
  demand_level: "Peak" | "High" | "Med";
}

export interface LogisticsRow {
  order_id: number;
  user_name: string;
  user_email: string | null;
  user_initials: string;
  product_name: string;
  quantity: number;
  revenue: number;
  status: string;
  created_at: string | null;
}

export interface OwnerAnalytics {
  stats: OverviewStats;
  forecast: {
    range: ForecastRange;
    points: ForecastPoint[];
    historical_end_index: number;
  };
  products: TrendingProduct[];
  rows: LogisticsRow[];
}

export async function fetchAnalyticsDashboard(range: ForecastRange): Promise<OwnerAnalytics> {
  const res = await gatedFetch(apiUrl(`/owner/analytics?range=${range}&trend_limit=3&logistics_limit=20`));
  return res.json();
}

export async function fetchOverview(): Promise<{ stats: OverviewStats }> {
  const res = await gatedFetch(apiUrl("/owner/analytics/overview"));
  return res.json();
}

export async function fetchForecast(range: ForecastRange): Promise<{
  range: ForecastRange;
  points: ForecastPoint[];
  historical_end_index: number;
}> {
  const res = await gatedFetch(apiUrl(`/owner/analytics/forecast?range=${range}`));
  return res.json();
}

export async function fetchTrending(limit = 3): Promise<{ products: TrendingProduct[] }> {
  const res = await gatedFetch(apiUrl(`/owner/analytics/trending?limit=${limit}`));
  return res.json();
}

export async function fetchLogistics(limit = 20): Promise<{ rows: LogisticsRow[] }> {
  const res = await gatedFetch(apiUrl(`/owner/analytics/logistics?limit=${limit}`));
  return res.json();
}

export async function updateOrderStatus(orderId: number, status: string) {
  const body = new FormData();
  body.append("order_id", String(orderId));
  body.append("status", status);
  const res = await gatedFetch(apiUrl("/owner/orders/status"), { method: "POST", body });
  return res.json();
}

// ─── Campaign workflow (Curator AI) ───────────────────────────────────

export type CampaignTone = "punchy" | "editorial" | "technical";
export type CampaignLanguage = "en" | "ne";
export type CampaignChannel = "facebook" | "instagram";

export interface OwnerProduct {
  id: number;
  name: string;
  category: string;
  color: string;
  price: number;
  description: string;
  quantity: number;
  image_path: string;
  is_wearable: number;
}

export function renderDefaultCaption(p: OwnerProduct): string {
  const hashtag = (p.category || "SmartShop").replace(/\s+/g, "");
  const desc = p.description?.trim() || `${p.color ? p.color + " " : ""}${p.category || "product"}.`;
  return `${p.name} — available now at Rs. ${p.price.toLocaleString()}.\n${desc}\n#${hashtag} #SmartShop`;
}

export async function restyleCaption(
  productId: number,
  tone: CampaignTone,
  language: CampaignLanguage = "en",
) {
  const body = new FormData();
  body.append("product_id", String(productId));
  body.append("tone", tone);
  body.append("language", language);
  const res = await gatedFetch(apiUrl("/owner/campaign/caption/restyle"), { method: "POST", body });
  return res.json() as Promise<{ caption: string; tone: string; language: string }>;
}

export interface GenerateVisualOpts {
  productId: number;
  prompt: string;
  modelPhoto?: File | null;
  backgroundPhoto?: File | null;
  backgroundPreset?: string | null;
}

export async function generateCampaignVisual(opts: GenerateVisualOpts) {
  const body = new FormData();
  body.append("product_id", String(opts.productId));
  body.append("prompt", opts.prompt);
  if (opts.backgroundPreset) body.append("background_preset", opts.backgroundPreset);
  if (opts.modelPhoto) body.append("model_photo", opts.modelPhoto);
  if (opts.backgroundPhoto) body.append("background_photo", opts.backgroundPhoto);
  const res = await gatedFetch(apiUrl("/owner/campaign/visual/generate"), { method: "POST", body });
  return res.json() as Promise<{
    success: boolean;
    image_path?: string;
    image_url?: string;
    error?: string;
  }>;
}

export async function launchCampaign(
  imagePath: string,
  caption: string,
  channels: CampaignChannel[],
) {
  const body = new FormData();
  body.append("image_path", imagePath);
  body.append("caption", caption);
  body.append("channels", channels.join(","));
  const res = await gatedFetch(apiUrl("/owner/campaign/launch"), { method: "POST", body });
  return res.json() as Promise<{
    ok: boolean;
    deployed: string[];
    failed: { channel: string; error: string }[];
  }>;
}
