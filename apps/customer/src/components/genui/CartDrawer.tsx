"use client";

import { Minus, Plus, Trash2, ArrowRight, CheckCircle } from "lucide-react";
import { imageUrl, updateCartDirect, removeCartDirect, checkout } from "@/lib/api";
import { useState, useEffect } from "react";

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
}: {
  data: CartItem[] | { items?: CartItem[]; count?: number; total?: number };
  sessionId: string;
  onCartUpdate?: () => void;
  onSendMessage?: (msg: string) => void;
}) {
  const items: CartItem[] = Array.isArray(data) ? data : (data as any)?.items || [];
  const [localItems, setLocalItems] = useState<CartItem[]>(items);
  const [mounted, setMounted] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [checkingOut, setCheckingOut] = useState(false);
  const [orderResult, setOrderResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // Set mounted flag and sync initial data only once
  useEffect(() => {
    setMounted(true);
    if (items.length > 0) {
      setLocalItems(items);
    }
  }, []);

  // Use localItems only - never fall back to props.items which may be stale
  const displayItems = localItems;
  const validItems = displayItems.filter(item => item.quantity > 0);
  const total = validItems.reduce((s, i) => s + i.price * i.quantity, 0);

  async function handleQty(item: CartItem, delta: number) {
    setBusy(item.id);
    const newQty = item.quantity + delta;
    if (newQty <= 0) {
      // Don't remove item, just update quantity to 0
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
    setOrderResult(null);
    try {
      const res = await checkout(sessionId);
      if (res?.success) {
        setOrderResult({ ok: true, msg: res.message || "Order placed successfully!" });
        setLocalItems([]);
        onCartUpdate?.();
      } else {
        setOrderResult({ ok: false, msg: res?.message || "Checkout failed." });
      }
    } catch (err: any) {
      setOrderResult({ ok: false, msg: `Checkout failed: ${err.message}` });
    }
    setCheckingOut(false);
  }

  if (!validItems.length) {
    return (
      <div className="bg-surface-container-lowest rounded-2xl p-8 text-center border border-outline-variant/10 shadow-sm">
        <p className="font-headline text-sm text-on-surface-variant">Your selection is empty.</p>
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest rounded-[2rem] overflow-hidden shadow-sm border border-outline-variant/10">
      <div className="p-6 md:p-8 space-y-6">
        {validItems.map((item, i) => (
          <div key={item.id} className={`flex items-center gap-6 group ${i > 0 ? "pt-6 border-t border-outline-variant/10" : ""}`}>
            <div className="w-20 h-20 bg-surface-container rounded-xl overflow-hidden flex-shrink-0">
              {item.image_path ? (
                <img src={imageUrl(item.image_path)} alt={item.product_name} className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-on-surface-variant/30 font-headline text-xl">S</div>
              )}
            </div>
            <div className="flex-grow flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 className="font-headline font-bold text-on-surface tracking-tight">{item.product_name}</h3>
                {item.color && <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant mt-1">{item.color}</p>}
              </div>
              <div className="flex items-center gap-6">
                <div className="flex items-center bg-surface-container-low rounded-full px-1.5 py-1">
                  <button onClick={() => handleQty(item, -1)} disabled={busy === item.id}
                    className="w-8 h-8 flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-30">
                    <Minus size={14} />
                  </button>
                  <span className="w-8 text-center text-sm font-bold font-headline">{item.quantity}</span>
                  <button onClick={() => handleQty(item, 1)} disabled={busy === item.id}
                    className="w-8 h-8 flex items-center justify-center text-on-surface-variant hover:text-on-surface transition-colors disabled:opacity-30">
                    <Plus size={14} />
                  </button>
                </div>
                <div className="text-right">
                  <p className="font-headline font-bold text-on-surface">Rs. {(item.price * item.quantity).toFixed(2)}</p>
                  <button onClick={() => handleRemove(item)} disabled={busy === item.id}
                    className="text-[10px] font-label uppercase tracking-wider text-error mt-1 flex items-center gap-1 opacity-60 hover:opacity-100 transition-opacity disabled:opacity-30">
                    <Trash2 size={12} /> Remove
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}

        <div className="pt-6 border-t border-on-surface/5 space-y-2">
          <div className="flex justify-between text-sm text-on-surface-variant">
            <span>Subtotal</span>
            <span className="font-medium">Rs. {total.toFixed(2)}</span>
          </div>
          <div className="flex justify-between text-sm text-on-surface-variant">
            <span>Shipping</span>
            <span className="font-medium">Calculated at checkout</span>
          </div>
          <div className="flex justify-between pt-3">
            <span className="font-headline font-extrabold text-lg uppercase tracking-tight">Total</span>
            <span className="font-headline font-extrabold text-xl text-primary">Rs. {total.toFixed(2)}</span>
          </div>
        </div>

        {orderResult && (
          <div className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-headline ${orderResult.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
            {orderResult.ok && <CheckCircle size={16} />}
            {orderResult.msg}
          </div>
        )}
        <button
          onClick={handleCheckout}
          disabled={checkingOut || (orderResult?.ok ?? false)}
          className="w-full bg-primary hover:bg-primary-dim text-on-primary py-4 rounded-xl font-headline font-bold text-sm uppercase tracking-[0.2em] shadow-lg shadow-primary/10 transition-all active:scale-[0.98] flex items-center justify-center gap-3 group disabled:opacity-50"
        >
          {checkingOut ? "Placing Order..." : orderResult?.ok ? "Order Placed!" : "Proceed to Checkout"}
          {!checkingOut && !orderResult?.ok && <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />}
        </button>
      </div>
    </div>
  );
}
