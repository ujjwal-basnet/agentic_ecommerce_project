"use client";

import { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
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

export default function OrderHistory({ sessionId }: { sessionId: string }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [totalOrders, setTotalOrders] = useState(0);
  const [totalSpent, setTotalSpent] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const PER_PAGE = 5;

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
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return dateStr?.split(" ")[0] || "";
    }
  }

  if (loading) {
    return (
      <div className="bg-white rounded-[32px] p-10 text-center border border-[rgba(171,179,183,0.22)] shadow-[0_8px_30px_rgba(43,52,55,0.04)]">
        <p className="font-headline text-sm text-[#6b7280]">Loading order history...</p>
      </div>
    );
  }

  if (!orders.length) {
    return (
      <div className="bg-white rounded-[32px] p-10 text-center border border-[rgba(171,179,183,0.22)] shadow-[0_8px_30px_rgba(43,52,55,0.04)]">
        <p className="font-headline text-sm text-[#6b7280]">No orders yet. Start shopping!</p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">
      {/* Header with stats */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <h2 className="font-headline font-extrabold text-[clamp(1.75rem,3.5vw,2.8rem)] tracking-[-0.03em] leading-tight text-[#2b3437]">
            Orders Archive
          </h2>
          <p className="text-[#586064] mt-2 max-w-md text-sm">
            Your purchase history and order details.
          </p>
        </div>
        <div className="flex gap-3">
          <div className="bg-white border border-[rgba(171,179,183,0.22)] p-5 rounded-xl min-w-[140px] shadow-sm">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#586064] font-bold mb-1.5">Total Orders</p>
            <p className="font-headline font-extrabold text-2xl tracking-tight text-[#575e70]">{totalOrders}</p>
          </div>
          <div className="bg-white border border-[rgba(171,179,183,0.22)] p-5 rounded-xl min-w-[140px] shadow-sm">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[#586064] font-bold mb-1.5">Total Spent</p>
            <p className="font-headline font-extrabold text-2xl tracking-tight text-[#575e70]">
              Rs. {totalSpent >= 1000 ? `${(totalSpent / 1000).toFixed(1)}k` : totalSpent.toFixed(0)}
            </p>
          </div>
        </div>
      </div>

      {/* Orders table */}
      <div className="bg-white rounded-xl overflow-hidden border border-[rgba(171,179,183,0.22)] shadow-sm">
        {/* Table header (desktop) */}
        <div className="hidden md:grid grid-cols-12 gap-4 px-8 py-5 bg-[#f1f4f6] border-b border-gray-200">
          <div className="col-span-2 text-[10px] uppercase tracking-[0.2em] text-[#586064] font-bold">Placed On</div>
          <div className="col-span-2 text-[10px] uppercase tracking-[0.2em] text-[#586064] font-bold">Order Ref</div>
          <div className="col-span-4 text-[10px] uppercase tracking-[0.2em] text-[#586064] font-bold">Item Description</div>
          <div className="col-span-2 text-[10px] uppercase tracking-[0.2em] text-[#586064] font-bold">Status</div>
          <div className="col-span-2 text-right text-[10px] uppercase tracking-[0.2em] text-[#586064] font-bold">Amount</div>
        </div>

        {/* Rows */}
        <div className="divide-y divide-gray-200">
          {paginated.map((order) => (
            <div
              key={order.id}
              className="grid grid-cols-1 md:grid-cols-12 gap-4 px-8 py-6 items-center hover:bg-gray-50 transition-colors duration-200"
            >
              {/* Date */}
              <div className="col-span-2 text-sm text-[#2b3437]">
                <span className="md:hidden text-[10px] uppercase tracking-[0.18em] text-[#586064] font-bold block mb-1">Placed On</span>
                {formatDate(order.created_at)}
              </div>

              {/* Order ref */}
              <div className="col-span-2">
                <span className="md:hidden text-[10px] uppercase tracking-[0.18em] text-[#586064] font-bold block mb-1">Order Ref</span>
                <span className="font-headline font-semibold text-xs tracking-[0.15em] text-[#575e70]">
                  #CR-{String(order.id).padStart(5, "0")}
                </span>
              </div>

              {/* Item description */}
              <div className="col-span-4 flex items-center gap-4">
                <div className="w-16 h-20 bg-[#eaeff1] flex-shrink-0 overflow-hidden rounded-lg">
                  {order.image_path ? (
                    <img
                      src={imageUrl(order.image_path)}
                      alt={order.product_name}
                      className="w-full h-full object-cover grayscale contrast-125"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-[#586064]/30 font-headline text-sm">S</div>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="font-headline font-bold text-base text-[#2b3437] truncate">{order.product_name}</p>
                  <p className="text-xs text-[#586064]">
                    Qty: {order.quantity} {order.category ? `• ${order.category}` : ""}
                  </p>
                </div>
              </div>

              {/* Status */}
              <div className="col-span-2">
                <span className="md:hidden text-[10px] uppercase tracking-[0.18em] text-[#586064] font-bold block mb-1">Status</span>
                <span className={`inline-flex items-center px-3 py-1 rounded-full text-[10px] uppercase tracking-[0.12em] font-bold ${
                  order.status === "delivered"
                    ? "bg-[#575e70] text-white"
                    : order.status === "pending"
                    ? "bg-[#fef3c7] text-[#92400e]"
                    : "bg-[#e2e9ec] text-[#586064]"
                }`}>
                  {order.status}
                </span>
              </div>

              {/* Amount */}
              <div className="col-span-2 text-right">
                <span className="md:hidden text-[10px] uppercase tracking-[0.18em] text-[#586064] font-bold block mb-1">Amount</span>
                <span className="font-headline font-bold text-[#2b3437]">
                  Rs. {(order.price * order.quantity).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 pt-2">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="w-10 h-10 flex items-center justify-center rounded-full border border-gray-200 text-[#2b3437] hover:bg-[#eaeff1] transition-colors disabled:opacity-30"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-xs font-bold tracking-[0.15em]">{page} / {totalPages}</span>
          <button
            onClick={() => setPage(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="w-10 h-10 flex items-center justify-center rounded-full border border-gray-200 text-[#2b3437] hover:bg-[#eaeff1] transition-colors disabled:opacity-30"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
