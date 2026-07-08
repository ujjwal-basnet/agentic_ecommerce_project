"use client";

import { ShoppingBag, ChevronLeft, ChevronRight, Sparkles, Check, Star } from "lucide-react";
import { addToCartDirect, imageUrl, trackView } from "@/lib/api";
import { useEffect, useState, useRef, useCallback } from "react";
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

// Colour swatch lookup — maps product colour name → CSS background
const COLOR_SWATCHES: Record<string, string> = {
  red: "#ff3b30",
  blue: "#007aff",
  royal: "#0047ab",
  navy: "#001f5b",
  black: "#1c1c1e",
  white: "#f5f5f7",
  green: "#34c759",
  silver: "#aeaeb2",
  grey: "#8e8e93",
  gray: "#8e8e93",
  cream: "#fffbeb",
  yellow: "#ffcc00",
  pink: "#ff2d55",
  purple: "#bf5af2",
  orange: "#ff9500",
  brown: "#795548",
};

function colorSwatch(color?: string): string | null {
  if (!color) return null;
  const lower = color.toLowerCase().trim();
  for (const [key, hex] of Object.entries(COLOR_SWATCHES)) {
    if (lower.includes(key)) return hex;
  }
  return null;
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
  const [adding, setAdding] = useState<number | null>(null);
  const [added, setAdded] = useState<Set<number>>(new Set());
  const [tryOnProduct, setTryOnProduct] = useState<Product | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollL, setCanScrollL] = useState(false);
  const [canScrollR, setCanScrollR] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

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

  const checkScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollL(el.scrollLeft > 4);
    setCanScrollR(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
    // Update active dot based on scroll position
    const cardWidth = 216; // 200px + 16px gap
    const idx = Math.round(el.scrollLeft / cardWidth);
    setActiveIndex(Math.min(idx, products.length - 1));
  }, [products.length]);

  useEffect(() => {
    checkScroll();
    const el = scrollRef.current;
    if (el) el.addEventListener("scroll", checkScroll, { passive: true });
    return () => el?.removeEventListener("scroll", checkScroll);
  }, [products, checkScroll]);

  function scrollBy(dir: number) {
    scrollRef.current?.scrollBy({ left: dir * 216, behavior: "smooth" });
  }

  function scrollToCard(index: number) {
    scrollRef.current?.scrollTo({ left: index * 216, behavior: "smooth" });
  }

  async function handleAdd(p: Product) {
    setAdding(p.id);
    try {
      await addToCartDirect(sessionId, p.name, p.price, 1);
      setAdded((prev) => new Set(prev).add(p.id));
      onCartUpdate?.();
      // Auto-reset "Added" state after 3 seconds
      setTimeout(() => {
        setAdded((prev) => {
          const next = new Set(prev);
          next.delete(p.id);
          return next;
        });
      }, 3000);
    } catch {}
    setTimeout(() => setAdding(null), 400);
  }

  if (!products.length) {
    return (
      <div className="bg-white rounded-2xl p-8 text-center shadow-card border border-[#f0f0f0]">
        <ShoppingBag size={28} className="text-[#d1d1d6] mx-auto mb-3" />
        <p className="text-[14px] text-[#86868b] font-body">No products found. Try a different search.</p>
      </div>
    );
  }

  const showArrows = products.length > 2;

  return (
    <>
      {tryOnProduct && (
        <TryOnModal product={tryOnProduct} onClose={() => setTryOnProduct(null)} onTryOnResult={onTryOnResult} />
      )}

      <div className="relative">
        {/* Left Scroll Arrow */}
        {showArrows && canScrollL && (
          <button
            onClick={() => scrollBy(-1)}
            aria-label="Scroll left"
            className="absolute left-0 top-[45%] -translate-y-1/2 -translate-x-3 z-10 w-8 h-8 bg-white rounded-full shadow-card-hover flex items-center justify-center text-[#1d1d1f] hover:bg-[#f5f5f7] active:scale-95 transition-all"
          >
            <ChevronLeft size={16} />
          </button>
        )}
        {/* Right Scroll Arrow */}
        {showArrows && canScrollR && (
          <button
            onClick={() => scrollBy(1)}
            aria-label="Scroll right"
            className="absolute right-0 top-[45%] -translate-y-1/2 translate-x-3 z-10 w-8 h-8 bg-white rounded-full shadow-card-hover flex items-center justify-center text-[#1d1d1f] hover:bg-[#f5f5f7] active:scale-95 transition-all"
          >
            <ChevronRight size={16} />
          </button>
        )}

        {/* Product carousel */}
        <div
          ref={scrollRef}
          className="flex gap-3 overflow-x-auto no-scrollbar pb-1 scroll-smooth"
        >
          {products.map((p) => {
            const isAdded = added.has(p.id);
            const isBusy = adding === p.id;
            const swatch = colorSwatch(p.color);
            const isLowStock = p.quantity !== undefined && p.quantity > 0 && p.quantity < 5;
            const isOutOfStock = p.quantity !== undefined && p.quantity === 0;

            return (
              <div
                key={p.id}
                className="flex-shrink-0 w-[200px] bg-white rounded-2xl overflow-hidden shadow-card hover:shadow-card-hover transition-all duration-300 group border border-transparent hover:border-[#e5e5ea]"
              >
                {/* Image */}
                <div className="aspect-[4/5] bg-[#f5f5f7] overflow-hidden relative">
                  {p.image_path ? (
                    <img
                      src={imageUrl(p.image_path)}
                      alt={p.name}
                      className="w-full h-full object-cover group-hover:scale-[1.04] transition-transform duration-500 ease-out"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-[#f5f5f7] to-[#ebebeb]">
                      {swatch ? (
                        <div
                          className="w-12 h-12 rounded-full shadow-inner border-2 border-white/60"
                          style={{ background: swatch }}
                        />
                      ) : (
                        <ShoppingBag size={24} className="text-[#d1d1d6]" />
                      )}
                      {p.category && (
                        <span className="text-[10px] text-[#86868b] font-label uppercase tracking-widest">
                          {p.category}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Try on badge */}
                  {p.is_wearable && !isOutOfStock && (
                    <button
                      onClick={() => setTryOnProduct(p)}
                      className="absolute top-2 left-2 flex items-center gap-1 bg-white/90 backdrop-blur-sm text-[#1d1d1f] text-[10px] font-headline font-semibold px-2 py-1 rounded-full shadow-subtle hover:bg-white transition-colors"
                    >
                      <Sparkles size={9} />
                      Try on
                    </button>
                  )}

                  {/* Low stock badge */}
                  {isLowStock && (
                    <span className="absolute top-2 right-2 bg-[#ff3b30] text-white text-[9px] font-headline font-semibold px-1.5 py-0.5 rounded-full">
                      {p.quantity} left
                    </span>
                  )}

                  {/* Out of stock overlay */}
                  {isOutOfStock && (
                    <div className="absolute inset-0 bg-white/70 backdrop-blur-[2px] flex items-center justify-center">
                      <span className="bg-[#1d1d1f] text-white text-[10px] font-headline font-semibold px-3 py-1 rounded-full">
                        Out of stock
                      </span>
                    </div>
                  )}
                </div>

                {/* Info */}
                <div className="p-3">
                  <h4 className="font-headline font-semibold text-[13px] text-[#1d1d1f] leading-tight line-clamp-2 mb-1">
                    {p.name}
                  </h4>

                  {/* Color + category row */}
                  {(p.color || p.category) && (
                    <div className="flex items-center gap-1.5 mb-2">
                      {swatch && (
                        <span
                          className="w-2.5 h-2.5 rounded-full inline-block border border-black/10 flex-shrink-0"
                          style={{ background: swatch }}
                          title={p.color}
                        />
                      )}
                      <p className="text-[10px] text-[#86868b] font-label uppercase tracking-wider truncate">
                        {[p.color, p.category].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                  )}

                  {/* Description snippet */}
                  {p.description && (
                    <p className="text-[11px] text-[#6e6e73] font-body leading-snug line-clamp-2 mb-2">
                      {p.description}
                    </p>
                  )}

                  <div className="flex items-center justify-between mt-auto">
                    <span className="font-headline font-bold text-[14px] text-[#1d1d1f]">
                      Rs. {p.price.toLocaleString()}
                    </span>
                    <button
                      onClick={() => handleAdd(p)}
                      disabled={isBusy || isOutOfStock}
                      aria-label={isAdded ? "Added to cart" : `Add ${p.name} to cart`}
                      className={`px-3 py-1.5 rounded-full text-[11px] font-headline font-semibold transition-all duration-200 active:scale-95 disabled:opacity-50 flex items-center gap-1 ${
                        isAdded
                          ? "bg-[#34c759]/10 text-[#34c759] border border-[#34c759]/20"
                          : isOutOfStock
                          ? "bg-[#f5f5f7] text-[#86868b] border border-[#e5e5ea]"
                          : "bg-[#1d1d1f] text-white hover:bg-[#3a3a3c]"
                      }`}
                    >
                      {isAdded ? (
                        <>
                          <Check size={10} strokeWidth={3} />
                          Added
                        </>
                      ) : isBusy ? (
                        <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                      ) : (
                        "Add"
                      )}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Scroll indicator dots — active dot is filled */}
        {products.length > 1 && (
          <div className="flex justify-center gap-1.5 mt-3">
            {products.map((_, i) => (
              <button
                key={i}
                onClick={() => scrollToCard(i)}
                aria-label={`Go to product ${i + 1}`}
                className={`rounded-full transition-all duration-300 ${
                  i === activeIndex
                    ? "w-4 h-1.5 bg-[#1d1d1f]"
                    : "w-1.5 h-1.5 bg-[#d1d1d6] hover:bg-[#aeaeb2]"
                }`}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
