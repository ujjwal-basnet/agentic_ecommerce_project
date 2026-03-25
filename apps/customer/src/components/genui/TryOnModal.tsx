"use client";

import { useState, useRef } from "react";
import { X, Upload, Loader2 } from "lucide-react";
import { tryOnProduct, imageUrl } from "@/lib/api";

interface TryOnModalProps {
  product: { id: number; name: string; image_path?: string };
  onClose: () => void;
}

export default function TryOnModal({ product, onClose }: TryOnModalProps) {
  const [step, setStep] = useState<"upload" | "loading" | "result" | "error">("upload");
  const [preview, setPreview] = useState<string | null>(null);
  const [resultPath, setResultPath] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const selectedFile = useRef<File | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    selectedFile.current = file;
    setPreview(URL.createObjectURL(file));
  }

  async function handleSubmit() {
    if (!selectedFile.current) return;
    setStep("loading");
    try {
      const res = await tryOnProduct(product.id, selectedFile.current);
      if (res.success) {
        setResultPath(res.image_path);
        setStep("result");
      } else {
        setErrorMsg(res.error || "Try-on failed.");
        setStep("error");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Connection error.");
      setStep("error");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">Virtual Try-On</h3>
            <p className="text-xs text-gray-500 mt-0.5">{product.name}</p>
          </div>
          <button onClick={onClose} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-100 transition-colors">
            <X size={16} className="text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5">
          {step === "upload" && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">Upload your photo to see how <strong>{product.name}</strong> looks on you.</p>

              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />

              {!preview ? (
                <button
                  onClick={() => fileRef.current?.click()}
                  className="w-full border-2 border-dashed border-gray-300 rounded-xl py-10 flex flex-col items-center gap-2 hover:border-blue-400 hover:bg-blue-50/50 transition-colors"
                >
                  <Upload size={28} className="text-gray-400" />
                  <span className="text-sm font-medium text-gray-500">Click to upload your photo</span>
                  <span className="text-xs text-gray-400">JPG, PNG or WebP</span>
                </button>
              ) : (
                <div className="relative">
                  <img src={preview} alt="Your photo" className="w-full aspect-[3/4] object-cover rounded-xl" />
                  <button
                    onClick={() => { setPreview(null); selectedFile.current = null; }}
                    className="absolute top-2 right-2 w-7 h-7 bg-black/60 text-white rounded-full flex items-center justify-center hover:bg-black/80"
                  >
                    <X size={14} />
                  </button>
                </div>
              )}

              <button
                onClick={handleSubmit}
                disabled={!preview}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold py-3 rounded-xl transition-colors text-sm"
              >
                Generate Try-On
              </button>
            </div>
          )}

          {step === "loading" && (
            <div className="flex flex-col items-center gap-4 py-12">
              <Loader2 size={36} className="text-blue-500 animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium text-gray-700">Generating your try-on...</p>
                <p className="text-xs text-gray-400 mt-1">This may take 10-20 seconds</p>
              </div>
            </div>
          )}

          {step === "result" && (
            <div className="space-y-4">
              <img
                src={imageUrl(resultPath)}
                alt="Try-On Result"
                className="w-full rounded-xl shadow-sm"
              />
              <p className="text-center text-sm text-gray-500">Here&apos;s how <strong>{product.name}</strong> looks on you!</p>
              <button onClick={onClose} className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 rounded-xl transition-colors text-sm">
                Close
              </button>
            </div>
          )}

          {step === "error" && (
            <div className="space-y-4 py-4">
              <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{errorMsg}</div>
              <button
                onClick={() => { setStep("upload"); setErrorMsg(""); }}
                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold py-3 rounded-xl transition-colors text-sm"
              >
                Try Again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
