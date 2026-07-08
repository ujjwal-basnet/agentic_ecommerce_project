"use client";

import { useState, useRef, useEffect } from "react";
import { X, Upload, Loader2, ChevronDown } from "lucide-react";
import { tryOnProduct, imageUrl, fetchImageModels } from "@/lib/api";

interface ImageModel {
  id: string;
  label: string;
  description: string;
  supports_edit: boolean;
}

interface TryOnModalProps {
  product: { id: number; name: string; image_path?: string };
  onClose: () => void;
  onTryOnResult?: (imagePath: string, productName: string) => void;
}

const FALLBACK_MODELS: ImageModel[] = [
  { id: "nano_banana", label: "\u{1F193} Nano Banana 2", description: "FREE · Google · $0.08/img", supports_edit: true },
];

export default function TryOnModal({ product, onClose, onTryOnResult }: TryOnModalProps) {
  const [step, setStep] = useState<"upload" | "loading" | "result" | "error">("upload");
  const [preview, setPreview] = useState<string | null>(null);
  const [resultPath, setResultPath] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [selectedModel, setSelectedModel] = useState("nano_banana");
  const [models, setModels] = useState<ImageModel[]>(FALLBACK_MODELS);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const selectedFile = useRef<File | null>(null);

  useEffect(() => {
    fetchImageModels()
      .then((res) => {
        if (res.models?.length) {
          const filtered = res.models.filter((m) => m.id === "nano_banana");
          if (filtered.length) setModels(filtered);
        }
      })
      .catch(() => { });
  }, []);

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
      const res = await tryOnProduct(product.id, selectedFile.current, selectedModel);
      if (res.success) {
        setResultPath(res.image_path);
        setStep("result");
        onTryOnResult?.(res.image_path, product.name);
      } else {
        setErrorMsg(res.error || "Try-on failed.");
        setStep("error");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Connection error.");
      setStep("error");
    }
  }

  const currentModel = models.find((m) => m.id === selectedModel) || models[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-floating w-full max-w-md flex flex-col max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex-shrink-0 flex items-center justify-between px-5 py-4 border-b border-[#f5f5f7]">
          <div>
            <h3 className="font-headline font-semibold text-[14px] text-[#1d1d1f]">Virtual Try-On</h3>
            <p className="text-[12px] text-[#86868b] mt-0.5 font-body">{product.name}</p>
          </div>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-[#f5f5f7] transition-colors">
            <X size={15} className="text-[#86868b]" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 flex-1 min-h-0 overflow-y-auto">
          {step === "upload" && (
            <div className="space-y-4">
              <p className="text-[13px] text-[#86868b] font-body">Upload your photo to see how <strong className="text-[#1d1d1f]">{product.name}</strong> looks on you.</p>

              {/* Model Selector */}
              <div className="relative">
                <label className="block text-[10px] uppercase tracking-widest text-[#86868b] font-bold font-label mb-1.5">
                  AI Model
                </label>
                <button
                  type="button"
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="w-full flex items-center justify-between px-3 py-2.5 bg-[#f5f5f7] rounded-xl text-left transition-colors hover:bg-[#ebebed]"
                >
                  <div>
                    <span className="text-[13px] font-body font-medium text-[#1d1d1f]">{currentModel.label}</span>
                    <span className="text-[11px] text-[#86868b] ml-2 font-label">{currentModel.description}</span>
                  </div>
                  <ChevronDown size={14} className={`text-[#86868b] transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
                </button>

                {dropdownOpen && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-xl shadow-floating border border-[#e5e5ea] z-10 overflow-hidden">
                    {models.map((m) => (
                      <button
                        key={m.id}
                        onClick={() => { setSelectedModel(m.id); setDropdownOpen(false); }}
                        className={`w-full flex items-center justify-between px-3 py-2.5 text-left transition-colors hover:bg-[#f5f5f7] ${selectedModel === m.id ? "bg-[#f5f5f7]" : ""
                          }`}
                      >
                        <div>
                          <span className="text-[13px] font-body font-medium text-[#1d1d1f]">{m.label}</span>
                          <span className="text-[11px] text-[#86868b] ml-2 font-label">{m.description}</span>
                        </div>
                        {selectedModel === m.id && (
                          <span className="w-2 h-2 rounded-full bg-[#1d1d1f]" />
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Note about edit support */}
              {!currentModel.supports_edit && (
                <div className="bg-[#fffbeb] border border-[#fde68a] rounded-lg px-3 py-2 text-[11px] text-[#92400e] font-body">
                  This model doesn&apos;t support photo editing — it will auto-fallback to Gemini for try-on.
                </div>
              )}

              <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />

              {!preview ? (
                <button
                  onClick={() => fileRef.current?.click()}
                  className="w-full border-2 border-dashed border-[#e5e5ea] rounded-xl py-10 flex flex-col items-center gap-2 hover:border-[#d1d1d6] hover:bg-[#fafafa] transition-colors"
                >
                  <Upload size={24} className="text-[#c7c7cc]" />
                  <span className="text-[13px] font-body font-medium text-[#86868b]">Click to upload your photo</span>
                  <span className="text-[11px] text-[#c7c7cc] font-label">JPG, PNG or WebP</span>
                </button>
              ) : (
                <div className="relative">
                  <img src={preview} alt="Your photo" className="h-48 w-full object-contain bg-[#f5f5f7] rounded-xl" />
                  <button
                    onClick={() => { setPreview(null); selectedFile.current = null; }}
                    className="absolute top-2 right-2 w-7 h-7 bg-black/50 text-white rounded-full flex items-center justify-center hover:bg-black/70"
                  >
                    <X size={13} />
                  </button>
                </div>
              )}

              <button
                onClick={handleSubmit}
                disabled={!preview}
                className="w-full bg-[#1d1d1f] hover:bg-[#333336] disabled:bg-[#e5e5ea] disabled:text-[#c7c7cc] text-white font-headline font-semibold py-3 rounded-xl transition-colors text-[13px]"
              >
                Generate Try-On
              </button>
            </div>
          )}

          {step === "loading" && (
            <div className="flex flex-col items-center gap-4 py-12">
              <Loader2 size={28} className="text-[#86868b] animate-spin" />
              <div className="text-center">
                <p className="text-[13px] font-body font-medium text-[#1d1d1f]">Generating with {currentModel.label}...</p>
                <p className="text-[11px] text-[#c7c7cc] mt-1 font-label">This may take 10-30 seconds</p>
              </div>
            </div>
          )}

          {step === "result" && (
            <div className="space-y-4">
              <img src={imageUrl(resultPath)} alt="Try-On Result" className="w-full rounded-xl shadow-card" />
              <p className="text-center text-[13px] text-[#86868b] font-body">
                Here&apos;s how <strong className="text-[#1d1d1f]">{product.name}</strong> looks on you!
              </p>
              <button onClick={onClose} className="w-full bg-[#f5f5f7] hover:bg-[#e8e8ed] text-[#1d1d1f] font-headline font-semibold py-3 rounded-xl transition-colors text-[13px]">
                Close
              </button>
            </div>
          )}

          {step === "error" && (
            <div className="space-y-4 py-4">
              <div className="bg-[#fff2f0] border border-[#ffe0dc] rounded-xl p-4 text-[13px] text-[#d70015] font-body">{errorMsg}</div>
              <button
                onClick={() => { setStep("upload"); setErrorMsg(""); }}
                className="w-full bg-[#f5f5f7] hover:bg-[#e8e8ed] text-[#1d1d1f] font-headline font-semibold py-3 rounded-xl transition-colors text-[13px]"
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
