"use client";

import { imageUrl } from "@/lib/api";

export default function TryOnResult({
  data,
}: {
  data: any;
  sessionId: string;
  onCartUpdate?: () => void;
  onSendMessage?: (msg: string) => void;
}) {
  const success = data?.success !== false;
  const imagePath = data?.image_path || "";
  const error = data?.error || "";

  if (!success || !imagePath) {
    return (
      <div className="bg-error-container/10 border border-error/20 rounded-xl px-5 py-4 text-sm font-headline text-error">
        {error || "Virtual try-on failed. Please upload your photo first."}
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest rounded-2xl overflow-hidden shadow-sm border border-outline-variant/10 max-w-sm">
      <img
        src={imageUrl(imagePath)}
        alt="Virtual Try-On Result"
        className="w-full aspect-[4/5] object-cover"
      />
      <div className="p-4 text-center">
        <p className="font-headline text-sm text-on-surface-variant font-light">Here&apos;s how it looks on you.</p>
      </div>
    </div>
  );
}
