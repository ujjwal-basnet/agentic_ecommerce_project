"use client";

import { Plus, Check, Sparkles } from "lucide-react";
import { addToCartDirect, imageUrl, trackView } from "@/lib/api";
import { useEffect, useState, useRef } from "react";
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
  onTryOnResult,
}: {
  data: Product[];
  sessionId: string;
  onCartUpdate?: () => void;
  onSendMessage?: (msg: string) => void;
  onTryOnResult?: (imagePath: string, productName: string) => void;
}) {
  const products = Array.isArray(data) ? data : [];
  const [adding, setAdding] = useState<number | null>(null);
  const [added, setAdded] = useState<Set<number>>(new Set());
  const [tryOnProduct, setTryOnProduct] = useState<Product | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

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

  async function handleAdd(p: Product) {
    setAdding(p.id);
    try {
      await addToCartDirect(sessionId, p.name, p.price);
      setAdded((prev) => new Set(prev).add(p.id));
      onCartUpdate?.();
    } catch {}
    setTimeout(() => setAdding(null), 500);
  }

  if (!products.length) return null;

  return (
    <div>
      {tryOnProduct && (
        <TryOnModal product={tryOnProduct} onClose={() => setTryOnProduct(null)} onTryOnResult={onTryOnResult} />
      )}

      <p className="text-[11px] uppercase tracking-wider text-[#86868b] font-label font-medium mb-3">Picked for you</p>

      <div ref={scrollRef} className="flex gap-3 overflow-x-auto pb-1 no-scrollbar">
        {products.map((p) => {
          const isAdded = added.has(p.id);
          return (
            <div key={p.id} className="flex-shrink-0 w-[160px] bg-white rounded-2xl overflow-hidden shadow-card group">
              <div className="aspect-square bg-[#f5f5f7] overflow-hidden relative">
                {p.image_path ? (
                  <img src={imageUrl(p.image_path)} alt={p.name} className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-500" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[#d1d1d6] text-2xl font-headline">S</div>
                )}
                {p.is_wearable && (
                  <button onClick={() => setTryOnProduct(p)}
                    className="absolute top-2 left-2 flex items-center gap-1 bg-white/90 backdrop-blur-sm text-[#1d1d1f] text-[9px] font-headline font-semibold px-2 py-0.5 rounded-full shadow-subtle hover:bg-white transition-colors">
                    <Sparkles size={8} />
                    Try on
                  </button>
                )}
              </div>
              <div className="p-2.5">
                <h4 className="font-headline text-[12px] font-medium text-[#1d1d1f] truncate">{p.name}</h4>
                {p.color && <p className="text-[9px] text-[#86868b] font-label uppercase tracking-wider">{p.color}</p>}
                <div className="flex items-center justify-between mt-1.5">
                  <span className="font-headline font-semibold text-[12px] text-[#1d1d1f]">Rs. {p.price.toLocaleString()}</span>
                  <button
                    onClick={() => handleAdd(p)}
                    disabled={adding === p.id}
                    className={`w-6 h-6 rounded-full flex items-center justify-center transition-all active:scale-95 disabled:opacity-50 ${
                      isAdded ? "bg-[#f5f5f7] text-[#86868b]" : "bg-[#1d1d1f] text-white"
                    }`}
                  >
                    {isAdded ? <Check size={11} /> : <Plus size={12} />}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
