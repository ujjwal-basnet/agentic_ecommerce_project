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

  // Track previous items to detect actual data changes from parent
  const prevItemsRef = useRef<CartItem[]>([]);
  useEffect(() => {
    setMounted(true);
    // Only update if items actually changed (new data from parent)
    const itemsChanged = items.length !== prevItemsRef.current.length ||
      items.some((item, i) => item.id !== prevItemsRef.current[i]?.id);
    if (itemsChanged) {
      prevItemsRef.current = items;
      setLocalItems(items);
    }
  }, [items]);

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

  const orderDone = data?.__orderDone;
  if (orderDone) {
    const cd = orderDone;
    return (
      <div className="bg-surface-container-lowest rounded-[2rem] overflow-hidden shadow-sm border border-outline-variant/10">
        <div className="p-6 md:p-8 space-y-6">
          <div className="flex flex-col items-center gap-3 py-4">
            <div className="w-14 h-14 rounded-full bg-green-50 flex items-center justify-center">
              <CheckCircle size={28} className="text-green-600" />
            </div>
            <h3 className="font-headline font-bold text-lg text-on-surface tracking-tight">Order Confirmed</h3>
            <p className="font-headline text-sm text-on-surface-variant text-center">{cd.msg}</p>
          </div>
          <div className="border-t border-outline-variant/10 pt-4 space-y-3">
            {cd.items.map((item: CartItem) => (
              <div key={item.id} className="flex items-center gap-4">
                <div className="w-12 h-12 bg-surface-container rounded-lg overflow-hidden flex-shrink-0">
                  {item.image_path ? (
                    <img src={imageUrl(item.image_path)} alt={item.product_name} className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-on-surface-variant/30 font-headline text-sm">S</div>
                  )}
                </div>
                <div className="flex-grow">
                  <p className="font-headline font-medium text-sm text-on-surface">{item.product_name}</p>
                  <p className="text-xs text-on-surface-variant">Qty: {item.quantity} × Rs. {item.price.toFixed(2)}</p>
                </div>
                <p className="font-headline font-bold text-sm text-on-surface">Rs. {(item.price * item.quantity).toFixed(2)}</p>
              </div>
            ))}
          </div>
          <div className="flex justify-between pt-4 border-t border-on-surface/5">
            <span className="font-headline font-extrabold text-base uppercase tracking-tight">Total Paid</span>
            <span className="font-headline font-extrabold text-lg text-primary">Rs. {cd.total.toFixed(2)}</span>
          </div>
        </div>
      </div>
    );
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

        <button
          onClick={handleCheckout}
          disabled={checkingOut}
          className="w-full bg-primary hover:bg-primary-dim text-on-primary py-4 rounded-xl font-headline font-bold text-sm uppercase tracking-[0.2em] shadow-lg shadow-primary/10 transition-all active:scale-[0.98] flex items-center justify-center gap-3 group disabled:opacity-50"
        >
          {checkingOut ? "Placing Order..." : "Proceed to Checkout"}
          {!checkingOut && <ArrowRight size={16} className="group-hover:translate-x-1 transition-transform" />}
        </button>
      </div>
    </div>
  );
}
