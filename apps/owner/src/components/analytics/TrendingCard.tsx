import { TrendingProduct } from "@/lib/api";
import { imageUrl } from "@/lib/api";

export function TrendingCard({ product }: { product: TrendingProduct }) {
  return (
    <div className="bg-surface-container-lowest rounded-xl overflow-hidden group">
      <div className="h-64 overflow-hidden relative bg-surface-container-low">
        {product.image_path ? (
          <img
            alt={product.name}
            src={imageUrl(product.image_path)}
            className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-on-surface-variant font-label text-xs uppercase tracking-widest">
            No image
          </div>
        )}
      </div>
      <div className="p-6">
        <div className="flex justify-between items-start mb-2 gap-3">
          <h4 className="font-headline text-lg text-on-background truncate">{product.name}</h4>
          <span className="font-label text-sm font-medium text-primary whitespace-nowrap">
            Rs. {product.price.toLocaleString()}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-4">
          <div className="w-full h-1 bg-surface-container-high rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-500"
              style={{ width: `${product.demand_pct}%` }}
            />
          </div>
          <span className="font-label text-xs text-on-surface-variant min-w-[32px] text-right">
            {product.demand_level}
          </span>
        </div>
      </div>
    </div>
  );
}
