"use client";

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import {
  Package, BarChart3, Settings, Plus, Minus, Trash2, RefreshCw,
  TrendingUp, ChevronLeft, ChevronRight, Search, Filter, X,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { fetchProducts, addProduct, deleteProduct, updateProduct, postToFacebook, imageUrl } from "@/lib/api";

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

type NavTab = "catalog" | "settings";

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
      const prods = await fetchProducts();
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

  async function handleQtyChange(pid: number, nextQty: number) {
    if (nextQty < 0) return;
    setProducts((prev) => prev.map((p) => (p.id === pid ? { ...p, quantity: nextQty } : p)));
    const form = new FormData();
    form.append("product_id", String(pid));
    form.append("quantity", String(nextQty));
    try {
      await updateProduct(form);
    } catch (e) {
      console.error("quantity update failed", e);
      loadAll();
    }
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

  const lowStock = products.filter((p) => p.quantity < 5 && p.quantity > 0);
  const outOfStock = products.filter((p) => p.quantity <= 0);

  return (
    <div className="flex min-h-screen bg-[#f8f9fa]">
      {/* ─── Sidebar ─────────────────────────────────────────── */}
      <Sidebar
        bottomCta={
          <button
            onClick={() => { setShowAdd(true); setNav("catalog"); }}
            className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-[#5B6278] to-[#7A8194] text-white rounded-xl py-3 font-headline font-bold text-[13px] hover:shadow-lg hover:shadow-[#5B6278]/20 transition-all duration-200"
          >
            <Plus size={16} /> New Entry
          </button>
        }
      />

      {/* ─── Main Content ────────────────────────────────────────── */}
      <main className="flex-1 overflow-auto">
        {/* Top bar */}
        <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-md border-b border-line px-8 py-3 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="text-sm text-muted-2 font-medium">Dashboard</span>
            <span className={`text-sm font-semibold cursor-pointer pb-0.5 ${nav === "catalog" ? "text-[#2b3437] border-b-2 border-[#2b3437]" : "text-muted-2 hover:text-[#2b3437]"}`} onClick={() => setNav("catalog")}>Catalog</span>
            <Link href="/analytics" className="text-sm font-semibold text-muted-2 hover:text-[#2b3437] pb-0.5">Analytics</Link>
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
              <div className="hidden md:grid grid-cols-[2.6fr_1.1fr_1.2fr_1.4fr_1fr_0.6fr] gap-4 px-2 mb-3 text-muted-2 text-[11px] uppercase tracking-[0.22em] font-bold">
                <div>Product Identity</div>
                <div>Category</div>
                <div>Stock Status</div>
                <div>Quantity</div>
                <div>Price</div>
                <div className="text-right">Action</div>
              </div>

              {/* Product rows */}
              <div className="space-y-3">
                {paginated.map((p) => (
                  <article key={p.id} className="bg-white rounded-[22px] p-4 shadow-[0_1px_1px_rgba(43,52,55,0.02)] grid grid-cols-1 md:grid-cols-[2.6fr_1.1fr_1.2fr_1.4fr_1fr_0.6fr] gap-4 items-center">
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

                    {/* Quantity editor */}
                    <div>
                      <div className="md:hidden text-[10px] uppercase tracking-[0.18em] text-muted-2 font-bold mb-1">Quantity</div>
                      <div className="inline-flex items-center gap-1 bg-soft rounded-full border border-line px-1 py-1">
                        <button
                          onClick={() => handleQtyChange(p.id, p.quantity - 1)}
                          disabled={p.quantity <= 0}
                          className="w-7 h-7 flex items-center justify-center rounded-full text-muted hover:bg-white hover:text-[#2b3437] transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Decrease"
                        >
                          <Minus size={12} />
                        </button>
                        <span className="min-w-[2rem] text-center font-headline font-bold text-sm text-[#2b3437] tabular-nums">
                          {p.quantity}
                        </span>
                        <button
                          onClick={() => handleQtyChange(p.id, p.quantity + 1)}
                          className="w-7 h-7 flex items-center justify-center rounded-full text-muted hover:bg-white hover:text-[#2b3437] transition-colors"
                          title="Increase"
                        >
                          <Plus size={12} />
                        </button>
                      </div>
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
