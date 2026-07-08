"use client";

import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, ShoppingBag } from "lucide-react";
import { fetchOrders, imageUrl } from "@/lib/api";

interface Order {
  id: number;
  product_name: string;
  category: string;
  price: number;
  quantity: number;
  status: string;
  created_at: string;
  image_path: string;
}

function StatusBadge({ status }: { status: string }) {
  const s = status?.toLowerCase();
  const styles: Record<string, string> = {
    delivered: "bg-[#f0fff4] text-[#0a6629]",
    pending: "bg-[#fff8ee] text-[#8a5100]",
    processing: "bg-[#f5f5f7] text-[#1d1d1f]",
    cancelled: "bg-[#fff2f0] text-[#d70015]",
    shipped: "bg-[#f0f5ff] text-[#1d3f8e]",
  };
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-headline font-semibold capitalize ${styles[s] || "bg-[#f5f5f7] text-[#86868b]"}`}>
      {status}
    </span>
  );
}

export default function OrderHistory({ sessionId }: { sessionId: string }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [totalOrders, setTotalOrders] = useState(0);
  const [totalSpent, setTotalSpent] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const PER_PAGE = 6;

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await fetchOrders(sessionId);
        setOrders(data.orders || []);
        setTotalOrders(data.total_orders || 0);
        setTotalSpent(data.total_spent || 0);
      } catch {
        console.error("Failed to load orders");
      }
      setLoading(false);
    }
    load();
  }, [sessionId]);

  const totalPages = Math.max(1, Math.ceil(orders.length / PER_PAGE));
  const paginated = orders.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  function formatDate(dateStr: string) {
    try {
      return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } catch {
      return dateStr?.split(" ")[0] || "";
    }
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-white rounded-2xl p-4 shadow-card animate-pulse">
            <div className="flex gap-3">
              <div className="w-12 h-12 rounded-xl bg-[#f5f5f7]" />
              <div className="flex-grow space-y-2">
                <div className="h-3.5 w-32 rounded bg-[#f5f5f7]" />
                <div className="h-3 w-20 rounded bg-[#f5f5f7]" />
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!orders.length) {
    return (
      <div className="bg-white rounded-2xl p-10 text-center shadow-card">
        <ShoppingBag size={28} className="text-[#d1d1d6] mx-auto mb-3" />
        <p className="font-headline font-medium text-[15px] text-[#1d1d1f] mb-1">No orders yet</p>
        <p className="text-[13px] text-[#86868b] font-body">Your orders will show up here.</p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-5 fade-in">
      <div>
        <h2 className="font-headline font-semibold text-[22px] tracking-tight text-[#1d1d1f]">Orders</h2>
        <p className="text-[13px] text-[#86868b] font-body mt-0.5">
          {totalOrders} order{totalOrders !== 1 ? "s" : ""} · Rs. {totalSpent >= 1000 ? `${(totalSpent / 1000).toFixed(1)}k` : totalSpent.toFixed(0)} total
        </p>
      </div>

      <div className="space-y-2">
        {paginated.map((order) => (
          <div key={order.id} className="bg-white rounded-2xl p-4 shadow-card hover:shadow-card-hover transition-all duration-200">
            <div className="flex gap-3">
              <div className="w-12 h-12 bg-[#f5f5f7] rounded-xl overflow-hidden flex-shrink-0">
                {order.image_path ? (
                  <img src={imageUrl(order.image_path)} alt={order.product_name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center"><ShoppingBag size={16} className="text-[#d1d1d6]" /></div>
                )}
              </div>

              <div className="flex-grow min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-headline font-medium text-[13px] text-[#1d1d1f] truncate">{order.product_name}</p>
                    <p className="text-[11px] text-[#86868b] font-label mt-0.5">
                      Qty {order.quantity} · {formatDate(order.created_at)}
                    </p>
                  </div>
                  <p className="font-headline font-semibold text-[13px] text-[#1d1d1f] flex-shrink-0">
                    Rs. {(order.price * order.quantity).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center justify-between mt-1.5">
                  <span className="text-[10px] text-[#c7c7cc] font-label">#{String(order.id).padStart(5, "0")}</span>
                  <StatusBadge status={order.status} />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-3 pt-1">
          <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}
            className="w-8 h-8 flex items-center justify-center rounded-full border border-[#e5e5ea] text-[#1d1d1f] hover:bg-[#f5f5f7] transition-all disabled:opacity-30">
            <ChevronLeft size={14} />
          </button>
          <span className="text-[11px] font-headline font-medium text-[#86868b]">{page} / {totalPages}</span>
          <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page === totalPages}
            className="w-8 h-8 flex items-center justify-center rounded-full border border-[#e5e5ea] text-[#1d1d1f] hover:bg-[#f5f5f7] transition-all disabled:opacity-30">
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
