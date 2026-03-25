"use client";

import { Plus } from "lucide-react";
import { addToCartDirect, imageUrl } from "@/lib/api";
import { useState } from "react";
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

export default function RecommendGrid({
  data,
  sessionId,
  onCartUpdate,
  onSendMessage,
}: {
  data: Product[];
  sessionId: string;
  onCartUpdate?: () => void;
  onSendMessage?: (msg: string) => void;
}) {
  const products = Array.isArray(data) ? data : [];
  const [adding, setAdding] = useState<number | null>(null);
  const [tryOnProduct, setTryOnProduct] = useState<Product | null>(null);

  async function handleAdd(p: Product) {
    setAdding(p.id);
    try {
      await addToCartDirect(sessionId, p.name, p.price);
      onCartUpdate?.();
    } catch {}
    setTimeout(() => setAdding(null), 600);
  }

  if (!products.length) return null;

  const tryOnModal = tryOnProduct ? (
    <TryOnModal product={tryOnProduct} onClose={() => setTryOnProduct(null)} />
  ) : null;

  return (
    <div>
      {tryOnModal}
      <div className="flex items-center gap-2 mb-4">
        <span className="w-1 h-1 rounded-full bg-primary/40" />
        <span className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant font-bold">Curated for you</span>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-2 no-scrollbar">
        {products.map((p) => (
          <div key={p.id} className="flex-shrink-0 w-44 bg-surface-container-lowest rounded-2xl overflow-hidden shadow-sm border border-outline-variant/10 group">
            <div className="aspect-square bg-surface-container-low overflow-hidden relative">
              {p.image_path ? (
                <img src={imageUrl(p.image_path)} alt={p.name} className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-500" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-on-surface-variant/30 font-headline text-3xl">S</div>
              )}
              {p.is_wearable && (
                <button onClick={() => setTryOnProduct(p)}
                  className="absolute top-2 left-2 bg-primary/80 text-on-primary text-[9px] font-label uppercase tracking-widest px-2 py-1 rounded-full hover:bg-primary transition-colors">
                  Try On
                </button>
              )}
            </div>
            <div className="p-3 space-y-2">
              <h4 className="font-headline text-xs font-semibold text-on-surface truncate">{p.name}</h4>
              {p.color && <p className="text-[9px] font-label uppercase tracking-widest text-on-surface-variant">{p.color}</p>}
              <div className="flex items-center justify-between">
                <span className="font-headline font-bold text-xs text-on-surface">Rs. {p.price}</span>
                <button onClick={() => handleAdd(p)} disabled={adding === p.id}
                  className="w-7 h-7 bg-primary hover:bg-primary-dim text-on-primary rounded-lg flex items-center justify-center transition-colors disabled:opacity-50 active:scale-95">
                  <Plus size={14} />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
