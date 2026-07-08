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
    <div className={`rounded-xl px-4 py-3 flex items-start gap-2.5 ${success ? "bg-[#f5f5f7]" : "bg-[#fff2f0]"}`}>
      <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${success ? "bg-[#e8e8ed] text-[#1d1d1f]" : "bg-[#ffe0dc] text-[#d70015]"}`}>
        {success ? <Check size={11} /> : <X size={11} />}
      </div>
      <div>
        <p className={`text-[13px] font-body font-medium ${success ? "text-[#1d1d1f]" : "text-[#d70015]"}`}>{message}</p>
        {success && count > 0 && (
          <p className="text-[11px] text-[#86868b] mt-0.5 font-label">
            {count} item{count !== 1 ? "s" : ""} · Rs. {Number(total).toLocaleString()}
          </p>
        )}
      </div>
    </div>
  );
}
