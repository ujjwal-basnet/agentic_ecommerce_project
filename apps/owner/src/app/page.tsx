"use client";

import { useState, useEffect, useCallback } from "react";
import {
  BarChart3, Package, DollarSign, Users, TrendingUp,
  Plus, Trash2, RefreshCw, AlertTriangle,
} from "lucide-react";
import { fetchAnalytics, fetchProducts, addProduct, deleteProduct, postToFacebook } from "@/lib/api";

interface Stats {
  total_products: number;
  total_orders: number;
  total_revenue: number;
  total_customers: number;
}

export default function OwnerDashboard() {
  const [tab, setTab] = useState<"overview" | "products" | "add">("overview");
  const [stats, setStats] = useState<Stats | null>(null);
  const [revenue, setRevenue] = useState<any[]>([]);
  const [topProducts, setTopProducts] = useState<any[]>([]);
  const [byCategory, setByCategory] = useState<any[]>([]);
  const [stock, setStock] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [fbPosting, setFbPosting] = useState(false);
  const [fbStatus, setFbStatus] = useState<{ ok: boolean; msg: string } | null>(null);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAnalytics(30);
      setStats(data.stats);
      setRevenue(data.revenue || []);
      setTopProducts(data.top || []);
      setByCategory(data.by_cat || []);
      setStock(data.stock || []);
      setOrders(data.orders || []);
    } catch (e) {
      console.error("Failed to load analytics", e);
    }
    setLoading(false);
  }, []);

  const loadProducts = useCallback(async () => {
    try {
      const data = await fetchProducts();
      setProducts(data || []);
    } catch {}
  }, []);

  useEffect(() => {
    loadAnalytics();
    loadProducts();
  }, [loadAnalytics, loadProducts]);

  async function handleDelete(pid: number) {
    if (!confirm("Delete this product?")) return;
    await deleteProduct(pid);
    loadProducts();
    loadAnalytics();
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
          setFbPosting(false);
        } else {
          const name = form.get("name") || "";
          const price = form.get("price") || "";
          const desc = form.get("description") || "";
          const caption = `${name} - Rs.${price}\n${desc}\n\nShop Now at SmartShop!`;
          const fbRes = await postToFacebook(imageFile, caption);
          if (fbRes?.success) {
            setFbStatus({ ok: true, msg: "Product added and posted to Facebook!" });
          } else {
            setFbStatus({ ok: false, msg: `Product added, but Facebook post failed: ${fbRes?.message || "Unknown error"}` });
          }
        }
      } catch (err: any) {
        setFbStatus({ ok: false, msg: `Product added, but Facebook post failed: ${err.message}` });
      }
      setFbPosting(false);
    } else {
      setFbStatus({ ok: true, msg: "Product added successfully!" });
    }

    formEl.reset();
    loadProducts();
    loadAnalytics();
    setTimeout(() => setFbStatus(null), 5000);
  }

  const lowStock = stock.filter((s) => s.quantity < 5);
  const maxRevenue = Math.max(...revenue.map((r) => r.revenue || 0), 1);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">SmartShop Dashboard</h1>
            <p className="text-xs text-gray-500">Owner Analytics & Management</p>
          </div>
          <button
            onClick={() => { loadAnalytics(); loadProducts(); }}
            className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 bg-gray-50 hover:bg-gray-100 px-3 py-1.5 rounded-lg transition-colors"
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white p-1 rounded-lg border border-gray-200 w-fit">
          {(["overview", "products", "add"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                tab === t ? "bg-brand-500 text-white" : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {t === "overview" ? "Overview" : t === "products" ? "Products" : "Add Product"}
            </button>
          ))}
        </div>

        {loading && tab === "overview" ? (
          <div className="text-center py-20 text-gray-400">Loading analytics...</div>
        ) : tab === "overview" ? (
          <div className="space-y-6">
            {/* Stat cards */}
            {stats && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <StatCard icon={<DollarSign size={20} />} label="Revenue" value={`Rs. ${stats.total_revenue.toLocaleString()}`} color="emerald" />
                <StatCard icon={<BarChart3 size={20} />} label="Orders" value={String(stats.total_orders)} color="blue" />
                <StatCard icon={<Package size={20} />} label="Products" value={String(stats.total_products)} color="purple" />
                <StatCard icon={<Users size={20} />} label="Customers" value={String(stats.total_customers)} color="amber" />
              </div>
            )}

            {/* Low stock alert */}
            {lowStock.length > 0 && (
              <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle size={16} className="text-orange-500" />
                  <span className="font-semibold text-sm text-orange-800">Low Stock Alert</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {lowStock.map((s: any) => (
                    <span key={s.id} className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded-full">
                      {s.name}: {s.quantity} left
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Revenue chart (simple bar) */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold text-sm mb-4 flex items-center gap-2">
                <TrendingUp size={16} className="text-brand-500" /> Revenue (Last 30 Days)
              </h3>
              {revenue.length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-8">No revenue data yet</p>
              ) : (
                <div className="flex items-end gap-1 h-40">
                  {revenue.map((r: any, i: number) => (
                    <div key={i} className="flex-1 flex flex-col items-center group relative">
                      <div
                        className="w-full bg-brand-500 rounded-t-sm hover:bg-brand-600 transition-colors min-h-[2px]"
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
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="font-semibold text-sm mb-3">Top Products</h3>
                <div className="space-y-2">
                  {topProducts.map((p: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400 w-4">#{i + 1}</span>
                        <span className="font-medium">{p.product_name}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-gray-500">
                        <span>{p.total_sold} sold</span>
                        <span className="text-emerald-600 font-medium">Rs. {p.revenue?.toFixed(0)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Revenue by category */}
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="font-semibold text-sm mb-3">Revenue by Category</h3>
                <div className="space-y-2">
                  {byCategory.map((c: any, i: number) => {
                    const totalCatRev = byCategory.reduce((s: number, x: any) => s + (x.revenue || 0), 0) || 1;
                    const pct = ((c.revenue || 0) / totalCatRev) * 100;
                    return (
                      <div key={i}>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="capitalize">{c.category}</span>
                          <span className="text-gray-500">Rs. {c.revenue?.toFixed(0)} ({pct.toFixed(0)}%)</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-2">
                          <div className="bg-brand-500 h-2 rounded-full" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Recent orders */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-semibold text-sm mb-3">Recent Orders</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b border-gray-100">
                      <th className="pb-2 font-medium">ID</th>
                      <th className="pb-2 font-medium">Product</th>
                      <th className="pb-2 font-medium">Qty</th>
                      <th className="pb-2 font-medium">Price</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium">Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map((o: any) => (
                      <tr key={o.id} className="border-b border-gray-50">
                        <td className="py-2 text-gray-400">#{o.id}</td>
                        <td className="py-2">{o.product_name}</td>
                        <td className="py-2">{o.quantity}</td>
                        <td className="py-2">Rs. {o.price}</td>
                        <td className="py-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            o.status === "delivered" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                          }`}>
                            {o.status}
                          </span>
                        </td>
                        <td className="py-2 text-gray-400 text-xs">{o.created_at?.split(" ")[0]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : tab === "products" ? (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-100 flex justify-between items-center">
              <h3 className="font-semibold text-sm">All Products ({products.length})</h3>
              <button onClick={() => setTab("add")} className="flex items-center gap-1 text-xs bg-brand-500 text-white px-3 py-1.5 rounded-lg hover:bg-brand-600 transition-colors">
                <Plus size={14} /> Add
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 bg-gray-50">
                    <th className="px-5 py-2.5 font-medium">ID</th>
                    <th className="px-5 py-2.5 font-medium">Name</th>
                    <th className="px-5 py-2.5 font-medium">Category</th>
                    <th className="px-5 py-2.5 font-medium">Color</th>
                    <th className="px-5 py-2.5 font-medium">Price</th>
                    <th className="px-5 py-2.5 font-medium">Stock</th>
                    <th className="px-5 py-2.5 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p: any) => (
                    <tr key={p.id} className="border-b border-gray-50 hover:bg-gray-50/50">
                      <td className="px-5 py-3 text-gray-400">{p.id}</td>
                      <td className="px-5 py-3 font-medium">{p.name}</td>
                      <td className="px-5 py-3">{p.category}</td>
                      <td className="px-5 py-3">{p.color}</td>
                      <td className="px-5 py-3">Rs. {p.price}</td>
                      <td className="px-5 py-3">
                        <span className={p.quantity < 5 ? "text-orange-600 font-medium" : ""}>
                          {p.quantity}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <button
                          onClick={() => handleDelete(p.id)}
                          className="text-red-400 hover:text-red-600 p-1 rounded transition-colors"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          /* Add Product form */
          <div className="bg-white rounded-xl border border-gray-200 p-6 max-w-lg">
            <h3 className="font-semibold text-sm mb-4">Add New Product</h3>
            <form onSubmit={handleAddProduct} className="space-y-4">
              <Field name="name" label="Product Name" required />
              <Field name="category" label="Category" required />
              <Field name="color" label="Color" />
              <Field name="price" label="Price (Rs.)" type="number" required />
              <Field name="quantity" label="Stock Quantity" type="number" required />
              <Field name="description" label="Description" />
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Image</label>
                <input type="file" name="image" accept="image/*" className="text-sm" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" name="is_wearable" id="is_wearable" value="true" className="rounded" />
                <label htmlFor="is_wearable" className="text-sm text-gray-600">Wearable (try-on eligible)</label>
              </div>
              <div className="flex items-center gap-2 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2.5">
                <input type="checkbox" name="post_facebook" id="post_facebook" value="true" className="rounded text-blue-600" />
                <label htmlFor="post_facebook" className="text-sm text-blue-700 font-medium">Post to Facebook</label>
              </div>
              {fbStatus && (
                <div className={`text-sm px-3 py-2 rounded-lg ${fbStatus.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
                  {fbStatus.msg}
                </div>
              )}
              <button
                type="submit"
                disabled={fbPosting}
                className="w-full bg-brand-500 hover:bg-brand-600 text-white py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {fbPosting ? "Posting to Facebook..." : "Add Product"}
              </button>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  const colors: Record<string, string> = {
    emerald: "bg-emerald-50 text-emerald-600",
    blue: "bg-blue-50 text-blue-600",
    purple: "bg-purple-50 text-purple-600",
    amber: "bg-amber-50 text-amber-600",
  };
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center mb-3 ${colors[color] || colors.blue}`}>
        {icon}
      </div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  );
}

function Field({ name, label, type = "text", required = false }: { name: string; label: string; type?: string; required?: boolean }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      <input
        name={name}
        type={type}
        required={required}
        className="w-full bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-brand-300 focus:ring-1 focus:ring-brand-100"
      />
    </div>
  );
}
