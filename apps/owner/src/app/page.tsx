"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Package, BarChart3, Settings, Plus, Trash2, RefreshCw,
  TrendingUp, ChevronLeft, ChevronRight, Search, Filter,
  DollarSign, Users, AlertTriangle, Pencil, X,
} from "lucide-react";
import { fetchAnalytics, fetchProducts, addProduct, deleteProduct, postToFacebook, imageUrl } from "@/lib/api";

/* ─── Types ──────────────────────────────────────────────────────────── */

interface Product {
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

interface Stats {
  total_products: number;
  total_orders: number;
  total_revenue: number;
  total_customers: number;
}

interface RevenueDay {
  date: string;
  revenue: number;
  orders: number;
}

interface TopProduct {
  product_name: string;
  total_sold: number;
  revenue: number;
}

interface CategoryRevenue {
  category: string;
  revenue: number;
}

interface StockItem {
  id: number;
  name: string;
  category: string;
  quantity: number;
  price: number;
}

interface Order {
  id: number;
  product_name: string;
  category: string;
  price: number;
  quantity: number;
  status: string;
  created_at: string;
}

type NavTab = "catalog" | "analytics" | "settings";

/* ─── Stock Chip ─────────────────────────────────────────────────────── */

function StockChip({ qty }: { qty: number }) {
  if (qty <= 0)
    return <span className="inline-flex items-center px-3 py-1.5 rounded-full bg-red-soft text-red-text text-[10px] font-extrabold uppercase tracking-[0.15em]">Out of Stock</span>;
  if (qty < 5)
    return <span className="inline-flex items-center px-3 py-1.5 rounded-full bg-blue-soft text-blue-text text-[10px] font-extrabold uppercase tracking-[0.15em]">Low Stock</span>;
  return <span className="inline-flex items-center px-3 py-1.5 rounded-full bg-purple-soft text-purple-text text-[10px] font-extrabold uppercase tracking-[0.15em]">In Stock</span>;
}

/* ─── Main ───────────────────────────────────────────────────────────── */

export default function OwnerDashboard() {
  const [nav, setNav] = useState<NavTab>("catalog");
  const [products, setProducts] = useState<Product[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [revenue, setRevenue] = useState<RevenueDay[]>([]);
  const [topProducts, setTopProducts] = useState<TopProduct[]>([]);
  const [byCategory, setByCategory] = useState<CategoryRevenue[]>([]);
  const [stock, setStock] = useState<StockItem[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [showAdd, setShowAdd] = useState(false);
  const [fbPosting, setFbPosting] = useState(false);
  const [fbStatus, setFbStatus] = useState<{ ok: boolean; msg: string } | null>(null);

  const PER_PAGE = 6;

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [analytics, prods] = await Promise.all([fetchAnalytics(30), fetchProducts()]);
      setStats(analytics.stats);
      setRevenue(analytics.revenue || []);
      setTopProducts(analytics.top || []);
      setByCategory(analytics.by_cat || []);
      setStock(analytics.stock || []);
      setOrders(analytics.orders || []);
      setProducts(prods || []);
    } catch (e) {
      console.error("Failed to load data", e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  async function handleDelete(pid: number) {
    if (!confirm("Delete this product?")) return;
    await deleteProduct(pid);
    loadAll();
  }

  async function handleAddProduct(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const form = new FormData(formEl);
    const shouldPostFb = form.get("post_facebook") === "true";
    form.delete("post_facebook");

    const res = await addProduct(form);
    if (!res?.success) {
      setFbStatus({ ok: false, msg: "Failed to add product." });
      return;
    }

    if (shouldPostFb) {
      setFbPosting(true);
      setFbStatus(null);
      try {
        const imageFile = (formEl.querySelector('input[name="image"]') as HTMLInputElement)?.files?.[0];
        if (!imageFile) {
          setFbStatus({ ok: false, msg: "Product added, but no image for Facebook post." });
        } else {
          const name = form.get("name") || "";
          const price = form.get("price") || "";
          const desc = form.get("description") || "";
          const caption = `${name} - Rs.${price}\n${desc}\n\nShop Now at SmartShop!`;
          const fbRes = await postToFacebook(imageFile, caption);
          setFbStatus(fbRes?.success
            ? { ok: true, msg: "Product added and posted to Facebook!" }
            : { ok: false, msg: `Product added, but Facebook post failed: ${fbRes?.message || "Unknown error"}` }
          );
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setFbStatus({ ok: false, msg: `Product added, but Facebook post failed: ${msg}` });
      }
      setFbPosting(false);
    } else {
      setFbStatus({ ok: true, msg: "Product added successfully!" });
    }

    formEl.reset();
    setShowAdd(false);
    loadAll();
    setTimeout(() => setFbStatus(null), 5000);
  }

  /* Filtered & paginated products */
  const filtered = products.filter((p) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return p.name.toLowerCase().includes(q) || p.category?.toLowerCase().includes(q) || p.color?.toLowerCase().includes(q);
  });
  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  const paginated = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  const lowStock = stock.filter((s) => s.quantity < 5 && s.quantity > 0);
  const outOfStock = stock.filter((s) => s.quantity <= 0);
  const maxRevenue = Math.max(...revenue.map((r) => r.revenue || 0), 1);

  return (
    <div className="flex min-h-screen bg-[#f8f9fa]">
      {/* ─── Sidebar ─────────────────────────────────────────────── */}
      <aside className="w-56 bg-white border-r border-line flex-shrink-0 flex flex-col">
        <div className="px-5 pt-6 pb-4">
          <h2 className="font-headline font-extrabold text-lg tracking-tight text-[#2b3437]">SmartShop</h2>
          <p className="text-[10px] uppercase tracking-[0.2em] text-muted-2 font-bold mt-0.5">Management</p>
        </div>
        <nav className="flex-1 px-3 space-y-1">
          <SidebarItem icon={<Package size={16} />} label="Inventory" active={nav === "catalog"} onClick={() => setNav("catalog")} />
          <SidebarItem icon={<BarChart3 size={16} />} label="Analytics" active={nav === "analytics"} onClick={() => setNav("analytics")} />
          <SidebarItem icon={<Settings size={16} />} label="Settings" active={nav === "settings"} onClick={() => setNav("settings")} />
        </nav>
        <div className="px-3 pb-6">
          <button
            onClick={() => { setShowAdd(true); setNav("catalog"); }}
            className="w-full flex items-center justify-center gap-2 bg-[#5b6478] text-white rounded-xl py-3 font-headline font-bold text-sm hover:bg-primary-dim transition-colors"
          >
            <Plus size={16} /> New Entry
          </button>
        </div>
      </aside>

      {/* ─── Main Content ────────────────────────────────────────── */}
      <main className="flex-1 overflow-auto">
        {/* Top bar */}
        <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-md border-b border-line px-8 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="text-sm text-muted-2 font-medium">Dashboard</span>
            <span className={`text-sm font-semibold cursor-pointer pb-0.5 ${nav === "catalog" ? "text-[#2b3437] border-b-2 border-[#2b3437]" : "text-muted-2 hover:text-[#2b3437]"}`} onClick={() => setNav("catalog")}>Catalog</span>
            <span className={`text-sm font-semibold cursor-pointer pb-0.5 ${nav === "analytics" ? "text-[#2b3437] border-b-2 border-[#2b3437]" : "text-muted-2 hover:text-[#2b3437]"}`} onClick={() => setNav("analytics")}>Analytics</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-2" />
              <input
                type="text"
                placeholder="Search catalog..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="pl-9 pr-4 py-2 bg-soft rounded-xl text-sm border border-line focus:outline-none focus:border-[#5b6478]/30 w-56 font-body"
              />
            </div>
            <button onClick={loadAll} className="p-2 text-muted-2 hover:text-[#2b3437] transition-colors" title="Refresh">
              <RefreshCw size={16} />
            </button>
          </div>
        </header>

        <div className="px-8 py-8">
          {loading ? (
            <div className="text-center py-20 text-muted-2 font-headline">Loading...</div>
          ) : nav === "catalog" ? (
            /* ─── CATALOG VIEW ───────────────────────────────────── */
            <>
              {/* Header */}
              <div className="flex items-end justify-between mb-8">
                <div>
                  <h1 className="font-headline font-extrabold text-[clamp(2rem,4vw,3.5rem)] leading-[0.95] tracking-[-0.03em]">Product Catalog</h1>
                  <p className="text-muted mt-2 text-[clamp(0.95rem,1.5vw,1.15rem)]">SmartShop — {products.length} products in inventory</p>
                </div>
                <div className="flex gap-3">
                  <button className="flex items-center gap-2 bg-soft border border-line rounded-2xl px-5 py-3.5 text-sm font-semibold text-[#2b3437] hover:bg-soft-2 transition-colors">
                    <Filter size={14} /> Filter
                  </button>
                  <button
                    onClick={() => setShowAdd(true)}
                    className="flex items-center gap-2 bg-[#5b6478] text-white rounded-2xl px-5 py-3.5 text-sm font-semibold shadow-[0_8px_24px_rgba(43,52,55,0.06)] hover:bg-primary-dim transition-colors"
                  >
                    <Plus size={14} /> Add Product
                  </button>
                </div>
              </div>

              {/* Table header (desktop) */}
              <div className="hidden md:grid grid-cols-[3fr_1.4fr_1.4fr_1fr_0.6fr] gap-4 px-2 mb-3 text-muted-2 text-[11px] uppercase tracking-[0.22em] font-bold">
                <div>Product Identity</div>
                <div>Category</div>
                <div>Stock Status</div>
                <div>Price</div>
                <div className="text-right">Action</div>
              </div>

              {/* Product rows */}
              <div className="space-y-3">
                {paginated.map((p) => (
                  <article key={p.id} className="bg-white rounded-[22px] p-4 shadow-[0_1px_1px_rgba(43,52,55,0.02)] grid grid-cols-1 md:grid-cols-[3fr_1.4fr_1.4fr_1fr_0.6fr] gap-4 items-center">
                    {/* Product identity */}
                    <div className="flex gap-4 items-center min-w-0">
                      <div className="w-16 h-20 flex-shrink-0 rounded-xl bg-[#eceeef] overflow-hidden">
                        {p.image_path ? (
                          <img src={imageUrl(p.image_path)} alt={p.name} className="w-full h-full object-cover" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-muted-2 text-xs">No img</div>
                        )}
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-headline font-bold text-[clamp(0.95rem,1.5vw,1.25rem)] tracking-[-0.02em] truncate">{p.name}</h3>
                        <p className="text-muted text-[clamp(0.8rem,1.1vw,0.95rem)] truncate">{p.category} {p.color ? `• ${p.color}` : ""}</p>
                      </div>
                    </div>

                    {/* Category (mobile label) */}
                    <div>
                      <div className="md:hidden text-[10px] uppercase tracking-[0.18em] text-muted-2 font-bold mb-1">Category</div>
                      <span className="text-sm capitalize">{p.category}</span>
                    </div>

                    {/* Stock status */}
                    <div>
                      <div className="md:hidden text-[10px] uppercase tracking-[0.18em] text-muted-2 font-bold mb-1">Stock</div>
                      <StockChip qty={p.quantity} />
                    </div>

                    {/* Price */}
                    <div>
                      <div className="md:hidden text-[10px] uppercase tracking-[0.18em] text-muted-2 font-bold mb-1">Price</div>
                      <span className="font-headline font-extrabold text-[clamp(1rem,1.6vw,1.5rem)] tracking-[-0.02em]">
                        Rs. {p.price.toLocaleString()}
                      </span>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-end gap-2">
                      <button onClick={() => handleDelete(p.id)} className="p-2 text-muted-2 hover:text-red-text transition-colors rounded-lg hover:bg-red-soft/30" title="Delete">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </article>
                ))}
              </div>

              {/* Pagination footer */}
              <div className="flex justify-between items-center mt-6 pt-6 border-t border-line">
                <p className="text-muted text-sm">Showing {(page - 1) * PER_PAGE + 1}-{Math.min(page * PER_PAGE, filtered.length)} of {filtered.length} products</p>
                <div className="flex items-center gap-2">
                  <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="w-10 h-10 rounded-xl border border-line flex items-center justify-center hover:bg-soft disabled:opacity-30 transition-colors">
                    <ChevronLeft size={16} />
                  </button>
                  {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((n) => (
                    <button
                      key={n}
                      onClick={() => setPage(n)}
                      className={`w-10 h-10 rounded-xl font-bold text-sm transition-colors ${page === n ? "bg-[#5b6478] text-white border-transparent" : "border border-line hover:bg-soft"}`}
                    >
                      {n}
                    </button>
                  ))}
                  <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages} className="w-10 h-10 rounded-xl border border-line flex items-center justify-center hover:bg-soft disabled:opacity-30 transition-colors">
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>

              {/* ─── Collection Insights ─────────────────────────── */}
              <section className="mt-16">
                <h2 className="font-headline font-extrabold text-[clamp(1.6rem,3vw,2.5rem)] tracking-[-0.03em] mb-6">Collection Insights</h2>
                <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-5">
                  {/* Demand card */}
                  <article className="bg-soft-2 rounded-3xl p-8 flex flex-col justify-between min-h-[220px]">
                    <div>
                      <div className="text-2xl text-[#5b6478] mb-3"><TrendingUp size={28} /></div>
                      <h3 className="font-headline font-extrabold text-[clamp(1.2rem,2vw,1.8rem)] tracking-[-0.02em] mb-2">Inventory Status</h3>
                      <p className="text-muted text-[clamp(0.9rem,1.2vw,1.05rem)] leading-relaxed max-w-[34ch]">
                        {lowStock.length > 0
                          ? `${lowStock.length} product${lowStock.length > 1 ? "s" : ""} running low on stock.`
                          : "All products are well stocked."
                        }
                      </p>
                    </div>
                    <div className="mt-6 flex justify-between items-end gap-3">
                      <span className="font-headline font-extrabold text-[clamp(2rem,4vw,3.5rem)] tracking-[-0.03em]">{products.length}</span>
                      <span className="text-[11px] uppercase tracking-[0.22em] text-muted-2 font-bold">Total SKUs</span>
                    </div>
                  </article>

                  {/* Dark inventory health card */}
                  <article className="bg-[#05080c] text-white rounded-3xl p-8 relative overflow-hidden min-h-[220px]">
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-7 relative z-10">
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.22em] text-[#9b9d9e] font-bold mb-2">Active SKUs</div>
                        <div className="font-headline font-extrabold text-[clamp(1.8rem,3vw,3rem)] tracking-[-0.03em]">
                          {products.filter((p) => p.quantity > 0).length}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.22em] text-[#9b9d9e] font-bold mb-2">Restock Required</div>
                        <div className="font-headline font-extrabold text-[clamp(1.8rem,3vw,3rem)] tracking-[-0.03em] text-[#fe8983]">
                          {lowStock.length + outOfStock.length}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.22em] text-[#9b9d9e] font-bold mb-2">Total Valuation</div>
                        <div className="font-headline font-extrabold text-[clamp(1.8rem,3vw,3rem)] tracking-[-0.03em]">
                          Rs. {(products.reduce((s, p) => s + p.price * p.quantity, 0) / 1000).toFixed(0)}k
                        </div>
                      </div>
                    </div>
                    {/* Glow effect */}
                    <div className="absolute right-0 bottom-0 w-56 h-56 rounded-full bg-[rgba(87,94,112,0.16)] blur-[80px] z-[1]" />
                  </article>
                </div>
              </section>
            </>
          ) : nav === "analytics" ? (
            /* ─── ANALYTICS VIEW ─────────────────────────────────── */
            <div className="space-y-8">
              <div>
                <h1 className="font-headline font-extrabold text-[clamp(2rem,4vw,3.5rem)] leading-[0.95] tracking-[-0.03em]">Analytics</h1>
                <p className="text-muted mt-2">Revenue, orders, and performance insights</p>
              </div>

              {/* Stat cards */}
              {stats && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <StatCard icon={<DollarSign size={20} />} label="Revenue" value={`Rs. ${stats.total_revenue.toLocaleString()}`} />
                  <StatCard icon={<BarChart3 size={20} />} label="Orders" value={String(stats.total_orders)} />
                  <StatCard icon={<Package size={20} />} label="Products" value={String(stats.total_products)} />
                  <StatCard icon={<Users size={20} />} label="Customers" value={String(stats.total_customers)} />
                </div>
              )}

              {/* Low stock alert */}
              {lowStock.length > 0 && (
                <div className="bg-[#fff7ed] border border-[#fed7aa] rounded-2xl p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle size={16} className="text-orange-500" />
                    <span className="font-headline font-bold text-sm text-orange-800">Low Stock Alert</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {lowStock.map((s) => (
                      <span key={s.id} className="text-xs bg-orange-100 text-orange-700 px-3 py-1.5 rounded-full font-medium">{s.name}: {s.quantity} left</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Revenue chart */}
              <div className="bg-white rounded-2xl border border-line p-6">
                <h3 className="font-headline font-bold text-sm mb-5 flex items-center gap-2">
                  <TrendingUp size={16} className="text-[#5b6478]" /> Revenue (Last 30 Days)
                </h3>
                {revenue.length === 0 ? (
                  <p className="text-muted-2 text-sm text-center py-12">No revenue data yet</p>
                ) : (
                  <div className="flex items-end gap-1 h-44">
                    {revenue.map((r, i) => (
                      <div key={i} className="flex-1 flex flex-col items-center group relative">
                        <div
                          className="w-full bg-[#5b6478] rounded-t-sm hover:bg-primary-dim transition-colors min-h-[2px]"
                          style={{ height: `${Math.max((r.revenue / maxRevenue) * 100, 2)}%` }}
                          title={`${r.date}: Rs. ${r.revenue?.toFixed(0)}`}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {/* Top products */}
                <div className="bg-white rounded-2xl border border-line p-6">
                  <h3 className="font-headline font-bold text-sm mb-4">Top Products</h3>
                  <div className="space-y-3">
                    {topProducts.map((p, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-muted-2 w-5 font-bold">#{i + 1}</span>
                          <span className="font-medium truncate max-w-[200px]">{p.product_name}</span>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-muted">
                          <span>{p.total_sold} sold</span>
                          <span className="text-[#5b6478] font-bold">Rs. {p.revenue.toFixed(0)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Revenue by category */}
                <div className="bg-white rounded-2xl border border-line p-6">
                  <h3 className="font-headline font-bold text-sm mb-4">Revenue by Category</h3>
                  <div className="space-y-3">
                    {byCategory.map((c, i) => {
                      const totalCatRev = byCategory.reduce((s, x) => s + (x.revenue || 0), 0) || 1;
                      const pct = ((c.revenue || 0) / totalCatRev) * 100;
                      return (
                        <div key={i}>
                          <div className="flex justify-between text-sm mb-1.5">
                            <span className="capitalize font-medium">{c.category}</span>
                            <span className="text-muted text-xs">Rs. {c.revenue?.toFixed(0)} ({pct.toFixed(0)}%)</span>
                          </div>
                          <div className="w-full bg-soft rounded-full h-2">
                            <div className="bg-[#5b6478] h-2 rounded-full transition-all" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Recent orders */}
              <div className="bg-white rounded-2xl border border-line p-6">
                <h3 className="font-headline font-bold text-sm mb-4">Recent Orders</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-muted-2 text-[10px] uppercase tracking-[0.18em] font-bold border-b border-line">
                        <th className="pb-3">ID</th>
                        <th className="pb-3">Product</th>
                        <th className="pb-3">Qty</th>
                        <th className="pb-3">Price</th>
                        <th className="pb-3">Status</th>
                        <th className="pb-3">Date</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map((o) => (
                        <tr key={o.id} className="border-b border-line/50">
                          <td className="py-3 text-muted-2 font-headline font-semibold">#{o.id}</td>
                          <td className="py-3 font-medium">{o.product_name}</td>
                          <td className="py-3">{o.quantity}</td>
                          <td className="py-3 font-headline font-bold">Rs. {o.price}</td>
                          <td className="py-3">
                            <span className={`text-[10px] uppercase tracking-wider font-bold px-3 py-1 rounded-full ${
                              o.status === "delivered" ? "bg-[#5b6478] text-white" : "bg-soft-2 text-muted"
                            }`}>
                              {o.status}
                            </span>
                          </td>
                          <td className="py-3 text-muted-2 text-xs">{o.created_at?.split(" ")[0]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            /* ─── SETTINGS VIEW ──────────────────────────────────── */
            <div>
              <h1 className="font-headline font-extrabold text-[clamp(2rem,4vw,3.5rem)] leading-[0.95] tracking-[-0.03em] mb-4">Settings</h1>
              <p className="text-muted">Store configuration and preferences coming soon.</p>
            </div>
          )}
        </div>
      </main>

      {/* ─── Add Product Modal ───────────────────────────────────── */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4" onClick={() => setShowAdd(false)}>
          <div className="bg-white rounded-3xl p-8 w-full max-w-lg max-h-[90vh] overflow-y-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-headline font-extrabold text-xl tracking-tight">Add New Product</h3>
              <button onClick={() => setShowAdd(false)} className="p-2 text-muted-2 hover:text-[#2b3437] transition-colors">
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleAddProduct} className="space-y-4">
              <Field name="name" label="Product Name" required />
              <div className="grid grid-cols-2 gap-4">
                <Field name="category" label="Category" required />
                <Field name="color" label="Color" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field name="price" label="Price (Rs.)" type="number" required />
                <Field name="quantity" label="Stock Quantity" type="number" required />
              </div>
              <Field name="description" label="Description" />
              <div>
                <label className="block text-[10px] uppercase tracking-[0.18em] text-muted-2 font-bold mb-2">Image</label>
                <input type="file" name="image" accept="image/*" className="text-sm w-full" />
              </div>
              <div className="flex items-center gap-3">
                <input type="checkbox" name="is_wearable" id="is_wearable" value="true" className="rounded" />
                <label htmlFor="is_wearable" className="text-sm text-muted">Wearable (try-on eligible)</label>
              </div>
              <div className="flex items-center gap-3 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
                <input type="checkbox" name="post_facebook" id="post_facebook" value="true" className="rounded text-blue-600" />
                <label htmlFor="post_facebook" className="text-sm text-blue-700 font-semibold">Post to Facebook</label>
              </div>
              {fbStatus && (
                <div className={`text-sm px-4 py-3 rounded-xl ${fbStatus.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                  {fbStatus.msg}
                </div>
              )}
              <button
                type="submit"
                disabled={fbPosting}
                className="w-full bg-[#5b6478] hover:bg-primary-dim text-white py-3.5 rounded-xl font-headline font-bold text-sm uppercase tracking-[0.15em] transition-colors disabled:opacity-50"
              >
                {fbPosting ? "Posting to Facebook..." : "Add Product"}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Sub-components ─────────────────────────────────────────────── */

function SidebarItem({ icon, label, active, onClick }: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors ${
        active ? "bg-[#5b6478] text-white" : "text-muted hover:bg-soft"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="bg-white rounded-2xl border border-line p-5">
      <div className="w-10 h-10 rounded-xl bg-soft-2 flex items-center justify-center mb-4 text-[#5b6478]">
        {icon}
      </div>
      <p className="font-headline font-extrabold text-2xl tracking-tight">{value}</p>
      <p className="text-xs text-muted-2 mt-1 uppercase tracking-[0.15em] font-bold">{label}</p>
    </div>
  );
}

function Field({ name, label, type = "text", required = false }: { name: string; label: string; type?: string; required?: boolean }) {
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-[0.18em] text-muted-2 font-bold mb-2">{label}</label>
      <input
        name={name}
        type={type}
        required={required}
        className="w-full bg-soft border border-line rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[#5b6478]/30 focus:ring-1 focus:ring-[#5b6478]/10 font-body"
      />
    </div>
  );
}
