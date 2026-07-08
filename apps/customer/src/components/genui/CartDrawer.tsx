"use client";

import { Minus, Plus, X, ArrowRight, CheckCircle, ShoppingBag } from "lucide-react";
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
  const [busy, setBusy] = useState<number | null>(null);
  const [checkingOut, setCheckingOut] = useState(false);

  const prevItemsRef = useRef<CartItem[]>([]);
  useEffect(() => {
    const itemsChanged =
      items.length !== prevItemsRef.current.length ||
      items.some((item, i) => item.id !== prevItemsRef.current[i]?.id);
    if (itemsChanged) {
      prevItemsRef.current = items;
      setLocalItems(items);
    }
  }, [items]);

  const validItems = localItems.filter((i) => i.quantity > 0);
  const total = validItems.reduce((s, i) => s + i.price * i.quantity, 0);

  async function handleQty(item: CartItem, delta: number) {
    setBusy(item.id);
    const newQty = item.quantity + delta;
    if (newQty <= 0) {
      await removeCartDirect(sessionId, item.product_name);
      setLocalItems((prev) => prev.filter((i) => i.id !== item.id));
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
        onOrderPlaced?.({ items: snapshot, total: snapshotTotal, msg: res.message || "Order placed successfully!" });
        setLocalItems([]);
        onCartUpdate?.();
        setCheckingOut(false);
        return;
      } else {
        alert(res?.message || "Checkout failed.");
      }
    } catch (err: any) {
      alert(`Checkout failed: ${err.message}`);
    }
    setCheckingOut(false);
  }

  /* ── Order confirmed ── */
  const orderDone = data?.__orderDone;
  if (orderDone) {
    const cd = orderDone;
    return (
      <div className="bg-white rounded-2xl overflow-hidden shadow-card">
        <div className="p-5 space-y-4">
          <div className="flex flex-col items-center gap-2 py-3">
            <div className="w-11 h-11 bg-[#f0fff4] rounded-full flex items-center justify-center">
              <CheckCircle size={22} className="text-[#34c759]" />
            </div>
            <h3 className="font-headline font-semibold text-[16px] text-[#1d1d1f]">Order Confirmed</h3>
            <p className="text-[13px] text-[#86868b] text-center font-body">{cd.msg}</p>
          </div>

          <div className="space-y-3 border-t border-[#f5f5f7] pt-3">
            {cd.items.map((item: CartItem) => (
              <div key={item.id} className="flex items-center gap-3">
                <div className="w-10 h-10 bg-[#f5f5f7] rounded-lg overflow-hidden flex-shrink-0">
                  {item.image_path ? (
                    <img src={imageUrl(item.image_path)} alt={item.product_name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center"><ShoppingBag size={14} className="text-[#d1d1d6]" /></div>
                  )}
                </div>
                <div className="flex-grow min-w-0">
                  <p className="font-headline font-medium text-[13px] text-[#1d1d1f] truncate">{item.product_name}</p>
                  <p className="text-[11px] text-[#86868b] font-label">Qty: {item.quantity}</p>
                </div>
                <p className="font-headline font-semibold text-[13px] text-[#1d1d1f] flex-shrink-0">Rs. {(item.price * item.quantity).toLocaleString()}</p>
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center pt-3 border-t border-[#f5f5f7]">
            <span className="font-headline font-medium text-[13px] text-[#86868b]">Total</span>
            <span className="font-headline font-semibold text-[16px] text-[#1d1d1f]">Rs. {cd.total.toLocaleString()}</span>
          </div>
        </div>
      </div>
    );
  }

  /* ── Empty ── */
  if (!validItems.length) {
    return (
      <div className="bg-white rounded-2xl p-8 text-center shadow-card">
        <ShoppingBag size={24} className="text-[#d1d1d6] mx-auto mb-2" />
        <p className="font-headline text-[14px] text-[#86868b]">Your cart is empty.</p>
      </div>
    );
  }

  /* ── Cart ── */
  return (
    <div className="bg-white rounded-2xl overflow-hidden shadow-card">
      <div className="p-5 space-y-0">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-headline font-semibold text-[16px] text-[#1d1d1f]">Cart</h2>
            <p className="text-[12px] text-[#86868b] font-body">{validItems.length} item{validItems.length !== 1 ? "s" : ""}</p>
          </div>
        </div>

        <div className="divide-y divide-[#f5f5f7]">
          {validItems.map((item) => (
            <div key={item.id} className="flex gap-3 py-3.5">
              <div className="w-14 h-14 bg-[#f5f5f7] rounded-xl overflow-hidden flex-shrink-0">
                {item.image_path ? (
                  <img src={imageUrl(item.image_path)} alt={item.product_name} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center"><ShoppingBag size={16} className="text-[#d1d1d6]" /></div>
                )}
              </div>

              <div className="flex-grow min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-headline font-medium text-[13px] text-[#1d1d1f] truncate">{item.product_name}</p>
                    {item.color && <p className="text-[10px] text-[#86868b] font-label uppercase tracking-wider mt-0.5">{item.color}</p>}
                  </div>
                  <p className="font-headline font-semibold text-[13px] text-[#1d1d1f] flex-shrink-0">
                    Rs. {(item.price * item.quantity).toLocaleString()}
                  </p>
                </div>

                <div className="flex items-center justify-between mt-2">
                  <div className="flex items-center bg-[#f5f5f7] rounded-full p-0.5">
                    <button onClick={() => handleQty(item, -1)} disabled={busy === item.id}
                      className="w-6 h-6 flex items-center justify-center text-[#86868b] hover:text-[#1d1d1f] rounded-full transition-colors disabled:opacity-30">
                      <Minus size={11} />
                    </button>
                    <span className="w-6 text-center text-[12px] font-headline font-semibold text-[#1d1d1f]">{item.quantity}</span>
                    <button onClick={() => handleQty(item, 1)} disabled={busy === item.id}
                      className="w-6 h-6 flex items-center justify-center text-[#86868b] hover:text-[#1d1d1f] rounded-full transition-colors disabled:opacity-30">
                      <Plus size={11} />
                    </button>
                  </div>
                  <button onClick={() => handleRemove(item)} disabled={busy === item.id}
                    className="text-[11px] text-[#86868b] hover:text-[#ff3b30] transition-colors font-body disabled:opacity-30">
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Summary */}
        <div className="pt-4 border-t border-[#f5f5f7] space-y-1.5">
          <div className="flex justify-between text-[13px]">
            <span className="text-[#86868b] font-body">Subtotal</span>
            <span className="font-headline font-medium text-[#1d1d1f]">Rs. {total.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-[13px]">
            <span className="text-[#86868b] font-body">Shipping</span>
            <span className="text-[#86868b] font-body text-[12px]">Calculated at checkout</span>
          </div>
          <div className="flex justify-between pt-2 border-t border-[#f5f5f7]">
            <span className="font-headline font-semibold text-[14px] text-[#1d1d1f]">Total</span>
            <span className="font-headline font-semibold text-[16px] text-[#1d1d1f]">Rs. {total.toLocaleString()}</span>
          </div>
        </div>

        <button
          onClick={handleCheckout}
          disabled={checkingOut}
          className="w-full mt-4 bg-[#1d1d1f] hover:bg-[#333336] text-white py-3 rounded-xl font-headline font-semibold text-[13px] transition-all active:scale-[0.99] disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {checkingOut ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Placing order...
            </>
          ) : (
            <>
              Checkout
              <ArrowRight size={14} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
