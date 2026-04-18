"use client";

import { useState } from "react";
import { updateOrderStatus } from "@/lib/api";

export type DeliveryStatus = "processing" | "shipped" | "in_transit";

const OPTIONS: { value: DeliveryStatus; label: string }[] = [
  { value: "processing", label: "Processing" },
  { value: "shipped", label: "Shipped" },
  { value: "in_transit", label: "In Transit" },
];

function normalize(s: string): DeliveryStatus {
  const k = s.toLowerCase().replace(/\s+/g, "_");
  if (k === "shipped") return "shipped";
  if (k === "in_transit") return "in_transit";
  return "processing";
}

function chipClass(status: DeliveryStatus): string {
  if (status === "in_transit") return "bg-surface-container-high text-on-surface";
  if (status === "shipped") return "bg-surface-container-lowest text-on-surface-variant ring-1 ring-outline-variant/30";
  return "bg-primary/10 text-primary";
}

interface Props {
  orderId: number;
  initialStatus: string;
}

export function StatusSelect({ orderId, initialStatus }: Props) {
  const [status, setStatus] = useState<DeliveryStatus>(normalize(initialStatus));
  const [saving, setSaving] = useState(false);

  async function onChange(next: DeliveryStatus) {
    const prev = status;
    setStatus(next);
    setSaving(true);
    try {
      const res = await updateOrderStatus(orderId, next);
      if (!res?.ok) setStatus(prev);
    } catch {
      setStatus(prev);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={`inline-flex items-center rounded-full px-1 ${chipClass(status)} ${saving ? "opacity-70" : ""}`}>
      <select
        value={status}
        onChange={(e) => onChange(e.target.value as DeliveryStatus)}
        disabled={saving}
        className="bg-transparent text-[10px] font-label tracking-wide uppercase px-2 py-1 outline-none cursor-pointer appearance-none pr-5"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 10 10'><path d='M2 4l3 3 3-3' stroke='currentColor' stroke-width='1.2' fill='none' stroke-linecap='round'/></svg>\")",
          backgroundRepeat: "no-repeat",
          backgroundPosition: "right 0.25rem center",
        }}
      >
        {OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-surface-container-lowest text-on-surface">
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
