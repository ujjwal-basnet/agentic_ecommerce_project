"use client";

import { Minus, Plus } from "lucide-react";
import { addToCartDirect, updateCartDirect, removeCartDirect, imageUrl, trackView } from "@/lib/api";
import { useEffect, useState } from "react";
import TryOnModal from "./TryOnModal";

interface Product {
  id: number;
  name: string;
  price: number;
  category?: string;
  color?: string;
  description?: string;
  image_path?: string;
  quantity?: number;
  is_wearable?: boolean;
}

export default function ProductList({
  data,
  sessionId,
  onCartUpdate,
  onSendMessage,
  onTryOnResult,
}: {
  data: Product[];
  sessionId: string;
  onCartUpdate?: () => void;
  onSendMessage?: (msg: string) => void;
  onTryOnResult?: (imagePath: string, productName: string) => void;
}) {
  const products = Array.isArray(data) ? data : [];
  const [qtys, setQtys] = useState<Record<number, number>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [tryOnProduct, setTryOnProduct] = useState<Product | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    const seen = new Set<number>();
    for (const p of products) {
      if (p?.id && !seen.has(p.id)) {
        seen.add(p.id);
        trackView(sessionId, p.id);
      }
    }
  }, [products, sessionId]);

  async function handleIncrement(p: Product) {
    setBusy(p.id);
    const cur = qtys[p.id] || 0;
    const next = cur + 1;
    try {
      if (cur === 0) {
        await addToCartDirect(sessionId, p.name, p.price, 1);
      } else {
        await updateCartDirect(sessionId, p.name, next);
      }
      setQtys((prev) => ({ ...prev, [p.id]: next }));
      onCartUpdate?.();
    } catch {}
    setBusy(null);
  }

  async function handleDecrement(p: Product) {
    const cur = qtys[p.id] || 0;
    if (cur <= 0) return;
    setBusy(p.id);
    const next = cur - 1;
    try {
      if (next === 0) {
        await removeCartDirect(sessionId, p.name);
      } else {
        await updateCartDirect(sessionId, p.name, next);
      }
      setQtys((prev) => ({ ...prev, [p.id]: next }));
      onCartUpdate?.();
    } catch {}
    setBusy(null);
  }

  if (!products.length) {
    return (
      <div className="bg-surface-container-lowest rounded-2xl p-8 text-center text-on-surface-variant border border-outline-variant/10 shadow-sm">
        <p className="font-headline text-sm">No products found. Try a different search.</p>
      </div>
    );
  }

  const tryOnModal = tryOnProduct ? (
    <TryOnModal product={tryOnProduct} onClose={() => setTryOnProduct(null)} onTryOnResult={onTryOnResult} />
  ) : null;

  const useCards = products.length <= 3;

  if (useCards) {
    return (
      <>{tryOnModal}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {products.map((p) => {
          const qty = qtys[p.id] || 0;
          return (
            <div key={p.id} className="bg-surface-container-lowest rounded-2xl overflow-hidden shadow-sm border border-outline-variant/10 group">
              <div className="aspect-[4/5] bg-surface-container-low overflow-hidden relative">
                {p.image_path ? (
                  <img src={imageUrl(p.image_path)} alt={p.name} className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-on-surface-variant/30 font-headline text-5xl">S</div>
                )}
                {p.is_wearable && (
                  <button
                    onClick={() => setTryOnProduct(p)}
                    className="absolute top-3 left-3 bg-primary/90 text-on-primary text-[10px] font-label uppercase tracking-widest px-3 py-1.5 rounded-full hover:bg-primary transition-colors shadow-md"
                  >
                    Try On
                  </button>
                )}
              </div>
              <div className="p-5 space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="font-headline font-semibold text-on-surface tracking-tight">{p.name}</h4>
                    {p.color && <p className="text-[10px] font-label uppercase tracking-widest text-on-surface-variant mt-1">{p.color}</p>}
                  </div>
                  <p className="font-headline font-bold text-on-surface whitespace-nowrap">Rs. {p.price}</p>
                </div>
                <div className="flex items-center gap-3 pt-1">
                  <div className="flex items-center bg-surface-container-low rounded-full px-1 py-1">
                    <button onClick={() => handleDecrement(p)} disabled={busy === p.id || qty === 0}
                      className="w-8 h-8 flex items-center justify-center text-on-surface-variant hover:text-on-surface disabled:opacity-30 transition-colors">
                      <Minus size={14} />
                    </button>
                    <span className="w-8 text-center text-sm font-bold font-headline">{qty}</span>
                    <button onClick={() => handleIncrement(p)} disabled={busy === p.id}
                      className="w-8 h-8 flex items-center justify-center text-on-surface-variant hover:text-on-surface disabled:opacity-30 transition-colors">
                      <Plus size={14} />
                    </button>
                  </div>
                  <button
                    onClick={() => handleIncrement(p)}
                    disabled={busy === p.id}
                    className="flex-1 bg-primary hover:bg-primary-dim text-on-primary py-2.5 rounded-lg font-headline font-bold text-xs uppercase tracking-[0.15em] transition-all active:scale-[0.98] disabled:opacity-50"
                  >
                    Add to Cart
                  </button>
                </div>
                {p.quantity !== undefined && p.quantity < 5 && p.quantity > 0 && (
                  <p className="text-[10px] font-label text-error">Only {p.quantity} left in stock</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
      </>
    );
  }

  return (
    <>{tryOnModal}
    <div className="bg-surface-container-lowest rounded-2xl p-6 md:p-8 shadow-sm border border-outline-variant/10">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-12 gap-y-1">
        {[products.slice(0, Math.ceil(products.length / 2)), products.slice(Math.ceil(products.length / 2))].map((col, ci) => (
          <div key={ci} className="flex flex-col">
            {col.map((p, i) => {
              const qty = qtys[p.id] || 0;
              return (
                <div key={p.id} className={`group flex items-center py-4 gap-4 transition-all duration-300 ${i > 0 ? "border-t border-outline-variant/10" : ""}`}>
                  <div className="w-20 h-20 bg-surface-container-low overflow-hidden rounded-lg flex-shrink-0 relative">
                    {p.image_path ? (
                      <img src={imageUrl(p.image_path)} alt={p.name} className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-on-surface-variant/30 font-headline text-xl">S</div>
                    )}
                    {p.is_wearable && (
                      <button
                        onClick={() => setTryOnProduct(p)}
                        className="absolute bottom-1 left-1 bg-primary/90 text-on-primary text-[8px] font-label uppercase tracking-widest px-2 py-1 rounded-full hover:bg-primary transition-colors shadow-md font-bold"
                      >
                        Try On
                      </button>
                    )}
                  </div>
                  <div className="flex-grow min-w-0">
                    <h4 className="font-headline text-sm font-semibold text-on-surface truncate">{p.name}</h4>
                    <p className="font-label text-xs text-on-surface-variant mt-0.5">Rs. {p.price}</p>
                  </div>
                  <div className="flex items-center bg-surface-container-low rounded-full px-1.5 py-1 flex-shrink-0">
                    <button onClick={() => handleDecrement(p)} disabled={busy === p.id || qty === 0}
                      className="w-6 h-6 flex items-center justify-center text-on-surface-variant hover:text-on-surface disabled:opacity-30 transition-colors">
                      <Minus size={12} />
                    </button>
                    <span className="px-1.5 text-xs font-bold font-headline w-6 text-center">{qty}</span>
                    <button onClick={() => handleIncrement(p)} disabled={busy === p.id}
                      className="w-6 h-6 flex items-center justify-center text-on-surface-variant hover:text-on-surface disabled:opacity-30 transition-colors">
                      <Plus size={12} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
    </>
  );
}
