"use client";

import { Check, X } from "lucide-react";

export default function CartConfirmation({
  data,
}: {
  data: any;
  sessionId: string;
  onCartUpdate?: () => void;
  onSendMessage?: (msg: string) => void;
}) {
  const success = data?.success !== false;
  const message = data?.message || data?.text || (success ? "Cart updated." : "Something went wrong.");
  const count = data?.count ?? data?.cart_total_items ?? 0;
  const total = data?.total ?? data?.cart_total_price ?? 0;

  return (
    <div className={`rounded-xl px-5 py-4 flex items-start gap-3 border ${success ? "bg-surface-container-lowest border-outline-variant/10" : "bg-error-container/10 border-error/20"}`}>
      <div className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${success ? "bg-primary/10 text-primary" : "bg-error/10 text-error"}`}>
        {success ? <Check size={14} /> : <X size={14} />}
      </div>
      <div>
        <p className={`text-sm font-headline font-medium ${success ? "text-on-surface" : "text-error"}`}>{message}</p>
        {success && count > 0 && (
          <p className="text-xs font-label text-on-surface-variant mt-1">
            {count} item{count !== 1 ? "s" : ""} in selection · Rs. {Number(total).toFixed(2)}
          </p>
        )}
      </div>
    </div>
  );
}
