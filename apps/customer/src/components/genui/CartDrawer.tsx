"use client";

import { Minus, Plus, Trash2, ArrowRight, CheckCircle } from "lucide-react";
import { imageUrl, updateCartDirect, removeCartDirect, checkout } from "@/lib/api";
import { useState, useEffect, useRef } from "react";

interface CartItem {
  id: number;
  product_name: string;
  price: number;
  quantity: number;
  image_path?: string;
  color?: string;
}

export default function CartDrawer({
  data,
  sessionId,
  onCartUpdate,
  onOrderPlaced,
}: {
  data: any;
  sessionId: string;
  onCartUpdate?: () => void;
  onSendMessage?: (msg: string) => void;
  onOrderPlaced?: (orderResult: any) => void;
}) {
  const items: CartItem[] = Array.isArray(data) ? data : (data as any)?.items || [];
  const [localItems, setLocalItems] = useState<CartItem[]>(items);
  const [mounted, setMounted] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [checkingOut, setCheckingOut] = useState(false);

  const prevItemsRef = useRef<CartItem[]>([]);
  useEffect(() => {
    setMounted(true);
    const itemsChanged = items.length !== prevItemsRef.current.length ||
      items.some((item, i) => item.id !== prevItemsRef.current[i]?.id);
    if (itemsChanged) {
      prevItemsRef.current = items;
      setLocalItems(items);
    }
  }, [items]);

  const displayItems = localItems;
  const validItems = displayItems.filter(item => item.quantity > 0);
  const total = validItems.reduce((s, i) => s + i.price * i.quantity, 0);

  async function handleQty(item: CartItem, delta: number) {
    setBusy(item.id);
    const newQty = item.quantity + delta;
    if (newQty <= 0) {
      await updateCartDirect(sessionId, item.product_name, 0);
      setLocalItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, quantity: 0 } : i)));
    } else {
      await updateCartDirect(sessionId, item.product_name, newQty);
      setLocalItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, quantity: newQty } : i)));
    }
    onCartUpdate?.();
    setBusy(null);
  }

  async function handleRemove(item: CartItem) {
    setBusy(item.id);
    await removeCartDirect(sessionId, item.product_name);
    setLocalItems((prev) => prev.filter((i) => i.id !== item.id));
    onCartUpdate?.();
    setBusy(null);
  }

  async function handleCheckout() {
    setCheckingOut(true);
    try {
      const snapshot = [...validItems];
      const snapshotTotal = total;
      const res = await checkout(sessionId);
      if (res?.success) {
        const orderResult = {
          items: snapshot,
          total: snapshotTotal,
          msg: res.message || "Order placed successfully!",
        };
        onOrderPlaced?.(orderResult);
        setLocalItems([]);
        setCheckingOut(false);
        onCartUpdate?.();
        return;
      } else {
        alert(res?.message || "Checkout failed.");
      }
    } catch (err: any) {
      alert(`Checkout failed: ${err.message}`);
    }
    setCheckingOut(false);
  }

  /* ─── Order Confirmed State ──────────────────────────────────── */
  const orderDone = data?.__orderDone;
  if (orderDone) {
    const cd = orderDone;
    return (
      <div className="bg-white rounded-[32px] overflow-hidden shadow-[0_8px_30px_rgba(43,52,55,0.04)] border border-[rgba(171,179,183,0.22)]">
        <div className="p-6 md:p-9 space-y-6">
          <div className="flex flex-col items-center gap-3 py-4">
            <div className="w-14 h-14 rounded-full bg-green-50 flex items-center justify-center">
              <CheckCircle size={28} className="text-green-600" />
            </div>
            <h3 className="font-headline font-extrabold text-xl tracking-tight text-[#2b3437]">Order Confirmed</h3>
            <p className="font-headline text-sm text-[#6b7280] text-center">{cd.msg}</p>
          </div>
          <div className="border-t border-[rgba(171,179,183,0.22)] pt-5 space-y-4">
            {cd.items.map((item: CartItem) => (
              <div key={item.id} className="flex items-center gap-4">
                <div className="w-14 h-14 bg-[#f3f4f6] rounded-[14px] overflow-hidden flex-shrink-0">
                  {item.image_path ? (
                    <img src={imageUrl(item.image_path)} alt={item.product_name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-[#6b7280]/30 font-headline text-sm">S</div>
                  )}
                </div>
                <div className="flex-grow min-w-0">
                  <p className="font-headline font-bold text-sm text-[#2b3437] truncate">{item.product_name}</p>
                  <p className="text-xs text-[#6b7280]">Qty: {item.quantity} × Rs. {item.price.toFixed(2)}</p>
                </div>
                <p className="font-headline font-extrabold text-sm text-[#2b3437]">Rs. {(item.price * item.quantity).toFixed(2)}</p>
              </div>
            ))}
          </div>
          <div className="flex justify-between pt-4 border-t border-[rgba(171,179,183,0.22)]">
            <span className="font-headline font-extrabold text-base uppercase tracking-[0.02em]">Total Paid</span>
            <span className="font-headline font-extrabold text-lg">Rs. {cd.total.toFixed(2)}</span>
          </div>
        </div>
      </div>
    );
  }

  /* ─── Empty Cart ─────────────────────────────────────────────── */
  if (!validItems.length) {
    return (
      <div className="bg-white rounded-[32px] p-10 text-center border border-[rgba(171,179,183,0.22)] shadow-[0_8px_30px_rgba(43,52,55,0.04)]">
        <p className="font-headline text-sm text-[#6b7280]">Your cart is empty.</p>
      </div>
    );
  }

  /* ─── Cart with Items ────────────────────────────────────────── */
  return (
    <div className="bg-white rounded-[32px] overflow-hidden shadow-[0_8px_30px_rgba(43,52,55,0.04)] border border-[rgba(171,179,183,0.22)]">
      <div className="p-6 md:p-9 space-y-0">
        {/* Header */}
        <div className="mb-6">
          <h2 className="font-headline font-extrabold text-[clamp(1.75rem,3vw,2.4rem)] leading-none tracking-[-0.03em] text-[#2b3437]">Cart</h2>
          <p className="mt-2 text-[#6b7280] text-[clamp(0.92rem,1.2vw,1rem)]">{validItems.length} item{validItems.length !== 1 ? "s" : ""} in your selection</p>
        </div>

        {/* Items */}
        <div className="space-y-0">
          {validItems.map((item, i) => (
            <div
              key={item.id}
              className={`flex gap-4 py-5 ${i > 0 ? "border-t border-[rgba(171,179,183,0.22)]" : ""}`}
            >
              {/* Thumbnail */}
              <div className="w-20 h-20 bg-[#f3f4f6] rounded-[14px] overflow-hidden flex-shrink-0">
                {item.image_path ? (
                  <img src={imageUrl(item.image_path)} alt={item.product_name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[#6b7280]/30 font-headline text-xl">S</div>
                )}
              </div>

              {/* Item details */}
              <div className="flex-grow min-w-0 flex flex-col gap-3">
                {/* Top row: name + price */}
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h3 className="font-headline font-bold text-[clamp(1rem,1.5vw,1.2rem)] tracking-[-0.02em] text-[#2b3437] truncate">{item.product_name}</h3>
                    {item.color && (
                      <p className="text-[11px] uppercase tracking-[0.14em] text-[#6b7280] mt-1">{item.color}</p>
                    )}
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="font-headline font-extrabold text-[clamp(1rem,1.6vw,1.15rem)] tracking-[-0.02em] text-[#2b3437]">
                      Rs. {(item.price * item.quantity).toFixed(2)}
                    </p>
                    <button
                      onClick={() => handleRemove(item)}
                      disabled={busy === item.id}
                      className="text-[#dc2626] text-[12px] mt-1 cursor-pointer hover:underline disabled:opacity-30"
                    >
                      Remove
                    </button>
                  </div>
                </div>

                {/* Quantity controls */}
                <div className="flex items-center">
                  <div className="inline-flex items-center bg-[#f3f4f6] rounded-full px-1 py-1 gap-0.5">
                    <button
                      onClick={() => handleQty(item, -1)}
                      disabled={busy === item.id}
                      className="w-9 h-9 flex items-center justify-center text-[#4b5563] hover:bg-[#e5e7eb] rounded-full transition-colors disabled:opacity-30"
                    >
                      <Minus size={14} />
                    </button>
                    <span className="min-w-[32px] text-center font-headline font-bold text-[15px]">{item.quantity}</span>
                    <button
                      onClick={() => handleQty(item, 1)}
                      disabled={busy === item.id}
                      className="w-9 h-9 flex items-center justify-center text-[#4b5563] hover:bg-[#e5e7eb] rounded-full transition-colors disabled:opacity-30"
                    >
                      <Plus size={14} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Summary */}
        <div className="pt-6 border-t border-[rgba(171,179,183,0.22)] space-y-3">
          <div className="flex justify-between items-center text-[15px] text-[#6b7280]">
            <span>Subtotal</span>
            <span className="font-semibold text-[#2b3437]">Rs. {total.toFixed(2)}</span>
          </div>
          <div className="flex justify-between items-center text-[15px] text-[#6b7280]">
            <span>Shipping</span>
            <span className="font-semibold text-[#2b3437]">Calculated at checkout</span>
          </div>
          <div className="flex justify-between items-center pt-3">
            <span className="font-headline font-extrabold text-[1.05rem] uppercase tracking-[0.02em]">Total</span>
            <span className="font-headline font-extrabold text-[clamp(1.15rem,1.8vw,1.4rem)] tracking-[-0.02em]">Rs. {total.toFixed(2)}</span>
          </div>
        </div>

        {/* Checkout button */}
        <button
          onClick={handleCheckout}
          disabled={checkingOut}
          className="w-full mt-6 bg-[#111827] hover:bg-[#1f2937] text-white py-4 rounded-2xl font-headline font-extrabold text-[14px] uppercase tracking-[0.18em] shadow-lg transition-all active:scale-[0.99] flex items-center justify-center gap-3 group disabled:opacity-50"
        >
          {checkingOut ? "Placing Order..." : "Proceed to Checkout"}
          {!checkingOut && <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />}
        </button>
      </div>
    </div>
  );
}
