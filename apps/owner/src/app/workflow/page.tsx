"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Package, BarChart3, Settings, Sparkles, Wand2, Palette, Send,
  CheckCircle2, Upload, Image as ImageIcon, RefreshCw, ArrowLeft, Loader2,
} from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import {
  fetchProducts,
  imageUrl,
  renderDefaultCaption,
  restyleCaption,
  generateCampaignVisual,
  launchCampaign,
  CampaignTone,
  CampaignLanguage,
  CampaignChannel,
  OwnerProduct,
} from "@/lib/api";

const TONES: { key: CampaignTone; label: string }[] = [
  { key: "punchy", label: "Punchy" },
  { key: "editorial", label: "Editorial" },
  { key: "technical", label: "Technical" },
];

const LANGUAGES: { key: CampaignLanguage; label: string }[] = [
  { key: "en", label: "English" },
  { key: "ne", label: "नेपाली" },
];

const PROMPT_TONES = [
  { id: "aesthetic", label: "Aesthetic" },
  { id: "cinematic", label: "Cinematic" },
  { id: "vintage", label: "Vintage" },
  { id: "minimalist", label: "Minimalist" },
  { id: "hyperrealistic", label: "Hyper-realistic" },
];

const IMAGE_MODELS = [
  { id: "nano_banana", label: "\u{1F193} Nano Banana 2", desc: "FREE · Google · $0.08/img" },
  { id: "gpt_image_2", label: "\u{1F193} GPT Image 2", desc: "FREE · OpenAI · $0.133/img" },
  { id: "flux_kontext_720", label: "FLUX Kontext 720p", desc: "Try-on · $0.025/img" },
  { id: "flux_kontext", label: "FLUX Kontext 1080p", desc: "Best quality · $0.025/img" },
  { id: "gptimage", label: "GPT Image 1", desc: "OpenAI · $0.02/img" },
];

export default function WorkflowPage() {
  // ── Source material ─────────────────────────────────────────────
  const [products, setProducts] = useState<OwnerProduct[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = useMemo(
    () => products.find((p) => p.id === selectedId) ?? null,
    [products, selectedId],
  );

  // ── Narrative ───────────────────────────────────────────────────
  const [caption, setCaption] = useState("");
  const [tone, setTone] = useState<CampaignTone>("editorial");
  const [language, setLanguage] = useState<CampaignLanguage>("en");
  const [restyling, setRestyling] = useState(false);

  // ── Visual treatment ────────────────────────────────────────────
  const [prompt, setPrompt] = useState(
    "Place product on a brutalist concrete pedestal. Dramatic, high-contrast studio lighting. Minimalist background, deep shadows.",
  );
  const [modelPhoto, setModelPhoto] = useState<File | null>(null);
  const [modelPreview, setModelPreview] = useState<string | null>(null);
  const [backgroundPhoto, setBackgroundPhoto] = useState<File | null>(null);
  const [backgroundPreview, setBackgroundPreview] = useState<string | null>(null);
  const [promptTone, setPromptTone] = useState<string>("aesthetic");
  const [generatingPrompt, setGeneratingPrompt] = useState(false);
  const [imageModel, setImageModel] = useState("nano_banana");
  const [variations, setVariations] = useState<{ image_path: string; image_url: string }[]>([]);
  const [activeVariant, setActiveVariant] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [visualError, setVisualError] = useState<string | null>(null);

  // ── Deploy ──────────────────────────────────────────────────────
  const [channels, setChannels] = useState<Record<CampaignChannel, boolean>>({
    facebook: true,
    instagram: true,
  });
  const [launching, setLaunching] = useState(false);
  const [launchResult, setLaunchResult] = useState<
    | { ok: boolean; deployed: string[]; failed: { channel: string; error: string }[] }
    | null
  >(null);

  // ── Load products ───────────────────────────────────────────────
  const loadProducts = useCallback(async () => {
    const prods = await fetchProducts();
    const list: OwnerProduct[] = prods || [];
    setProducts(list);
    if (!selectedId && list.length > 0) setSelectedId(list[0].id);
  }, [selectedId]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  // ── Default caption reflects current product selection ─────────
  useEffect(() => {
    if (selected) setCaption(renderDefaultCaption(selected));
  }, [selected]);

  // ── Active variation ───────────────────────────────────────────
  const activePreview = useMemo(() => {
    if (variations.length > 0) return variations[activeVariant]?.image_url ?? null;
    if (selected?.image_path) return imageUrl(selected.image_path);
    return null;
  }, [variations, activeVariant, selected]);

  // ── Handlers ───────────────────────────────────────────────────
  async function handleRestyle() {
    if (!selected) return;
    setRestyling(true);
    try {
      const res = await restyleCaption(selected.id, tone, language);
      if (res?.caption) setCaption(res.caption);
    } finally {
      setRestyling(false);
    }
  }

  function handleModelPhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setModelPhoto(file);
    if (modelPreview) URL.revokeObjectURL(modelPreview);
    setModelPreview(file ? URL.createObjectURL(file) : null);
  }

  function handleBackgroundPhotoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setBackgroundPhoto(file);
    if (backgroundPreview) URL.revokeObjectURL(backgroundPreview);
    setBackgroundPreview(file ? URL.createObjectURL(file) : null);
  }

  async function handleGeneratePrompt(toneOverride?: string, alsoGenerateImage?: boolean) {
    if (!selected) return;
    setGeneratingPrompt(true);
    try {
      const { generateCampaignVisualPrompt } = await import("@/lib/api");
      const res = await generateCampaignVisualPrompt(selected.id, toneOverride || promptTone);
      setPrompt(res.prompt);
      if (alsoGenerateImage) {
        // Also restyle caption with editorial tone
        restyleCaption(selected.id, tone, language).then((r) => {
          if (r?.caption) setCaption(r.caption);
        });
        // Trigger image generation with new prompt
        setGenerating(true);
        setVisualError(null);
        const genRes = await generateCampaignVisual({
          productId: selected.id,
          prompt: res.prompt,
          imageModel,
          modelPhoto,
          backgroundPhoto,
          backgroundPreset: null,
        });
        if (genRes.success && genRes.image_path && genRes.image_url) {
          const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
            .replace(/\/+$/, "")
            .replace(/\/api$/i, "");
          const fullUrl = genRes.image_url.startsWith("http") ? genRes.image_url : `${base}${genRes.image_url}`;
          setVariations((prev) => {
            const next = [...prev, { image_path: genRes.image_path!, image_url: fullUrl }];
            setActiveVariant(next.length - 1);
            return next;
          });
        } else {
          setVisualError(genRes.error || "Image generation failed");
        }
        setGenerating(false);
      }
    } catch (e) {
      console.error(e);
      setGenerating(false);
    } finally {
      setGeneratingPrompt(false);
    }
  }

  async function handleGenerate() {
    if (!selected) return;
    setGenerating(true);
    setVisualError(null);
    try {
      const res = await generateCampaignVisual({
        productId: selected.id,
        prompt,
        imageModel,
        modelPhoto,
        backgroundPhoto,
        backgroundPreset: null,
      });
      if (res.success && res.image_path && res.image_url) {
        const base = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
          .replace(/\/+$/, "")
          .replace(/\/api$/i, "");
        const fullUrl = res.image_url.startsWith("http") ? res.image_url : `${base}${res.image_url}`;
        setVariations((prev) => {
          const next = [...prev, { image_path: res.image_path!, image_url: fullUrl }];
          setActiveVariant(next.length - 1);
          return next;
        });
      } else {
        setVisualError(res.error || "Image generation failed");
      }
    } catch (e) {
      setVisualError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  }

  async function handleLaunch() {
    const active = variations[activeVariant];
    const launchImagePath = active?.image_path || selected?.image_path;
    if (!launchImagePath) {
      setLaunchResult({
        ok: false,
        deployed: [],
        failed: [{ channel: "preflight", error: "Select a product with an image first." }],
      });
      return;
    }
    const picked = (Object.keys(channels) as CampaignChannel[]).filter((k) => channels[k]);
    if (picked.length === 0) {
      setLaunchResult({
        ok: false,
        deployed: [],
        failed: [{ channel: "preflight", error: "Pick at least one channel." }],
      });
      return;
    }
    setLaunching(true);
    setLaunchResult(null);
    try {
      const res = await launchCampaign(launchImagePath, caption, picked);
      setLaunchResult(res);
    } catch (e) {
      setLaunchResult({
        ok: false,
        deployed: [],
        failed: [{ channel: "network", error: e instanceof Error ? e.message : String(e) }],
      });
    } finally {
      setLaunching(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="flex min-h-screen bg-[#f8f9fa] text-[#2b3437]">
      <Sidebar />

      {/* Main */}
      <main className="flex-1">
        <div className="max-w-5xl mx-auto px-6 md:px-10 pt-12 md:pt-20 pb-24 space-y-24">
          {/* Hero */}
          <div className="text-center space-y-4">
            <h1 className="text-5xl md:text-6xl font-headline font-extrabold tracking-tight">
              Social Automation
            </h1>
            <p className="text-[#586064] font-body text-sm max-w-md mx-auto">
              Curate, generate, and deploy high-end social campaigns effortlessly.
            </p>
          </div>

          {/* ── Section 1: Source Material ───────────────────── */}
          <section className="space-y-6">
            <div className="flex items-center justify-between border-b border-[#eaeff1] pb-4">
              <h2 className="font-headline text-2xl font-bold">1. Source Material</h2>
              <button
                onClick={loadProducts}
                className="text-sm font-bold tracking-widest uppercase text-[#575e70] hover:text-[#2b3437] transition-colors inline-flex items-center gap-1"
              >
                <RefreshCw size={14} /> Refresh
              </button>
            </div>

            {selected ? (
              <div className="bg-white rounded-2xl p-3 flex gap-6 items-center shadow-[0_12px_32px_rgba(43,52,55,0.04)] ring-1 ring-black/5">
                <div className="w-28 h-36 bg-[#eaeff1] overflow-hidden rounded-xl flex-shrink-0">
                  {selected.image_path ? (
                    <img
                      src={imageUrl(selected.image_path)}
                      alt={selected.name}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-[#586064] text-xs">
                      No image
                    </div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <span className="font-label text-[10px] uppercase tracking-widest text-[#586064] font-bold">
                    Selected Item
                  </span>
                  <h3 className="font-headline text-xl font-bold truncate">{selected.name}</h3>
                  <p className="font-body text-sm text-[#586064] truncate">
                    {selected.category} • SKU #{selected.id} • Rs. {selected.price.toLocaleString()}
                  </p>
                </div>
                <CheckCircle2 className="text-[#575e70] flex-shrink-0 mr-3" size={28} />
              </div>
            ) : (
              <div className="text-sm text-[#586064]">No products in inventory.</div>
            )}

            {/* Product picker strip */}
            <div className="flex gap-3 overflow-x-auto pb-2">
              {products.map((p) => {
                const active = p.id === selectedId;
                return (
                  <button
                    key={p.id}
                    onClick={() => setSelectedId(p.id)}
                    className={`flex-shrink-0 w-20 h-24 rounded-xl overflow-hidden ring-2 transition-all ${
                      active ? "ring-[#575e70] scale-105" : "ring-transparent opacity-60 hover:opacity-100"
                    }`}
                    title={p.name}
                  >
                    {p.image_path ? (
                      <img src={imageUrl(p.image_path)} alt={p.name} className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full bg-[#eaeff1] flex items-center justify-center text-[10px] text-[#586064] px-1 text-center">
                        {p.name}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </section>

          {/* ── Section 2: Narrative ─────────────────────────── */}
          <section className="space-y-6">
            <div className="flex items-center justify-between border-b border-[#eaeff1] pb-4">
              <h2 className="font-headline text-2xl font-bold">2. Narrative</h2>
              <div className="flex items-center gap-2 text-xs text-[#586064]">
                <Sparkles size={14} className="text-[#575e70]" /> AI Assisted
              </div>
            </div>
            <div className="bg-white rounded-2xl p-6 shadow-[0_12px_32px_rgba(43,52,55,0.04)] space-y-6 ring-1 ring-black/5">
              <textarea
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder="Start typing or generate narrative..."
                className="w-full bg-transparent border-none focus:ring-0 focus:outline-none resize-none font-body text-lg leading-relaxed text-[#2b3437] min-h-[140px]"
              />
              <div className="flex items-center justify-between pt-4 border-t border-[#eaeff1] gap-4 flex-wrap">
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2 flex-wrap">
                    {TONES.map((t) => {
                      const active = tone === t.key;
                      return (
                        <button
                          key={t.key}
                          onClick={() => setTone(t.key)}
                          className={`px-3 py-1 font-label text-[11px] uppercase tracking-widest rounded-full cursor-pointer transition-colors ${
                            active
                              ? "bg-[#575e70] text-white"
                              : "bg-[#eaeff1] text-[#586064] hover:bg-[#575e70] hover:text-white"
                          }`}
                        >
                          {t.label}
                        </button>
                      );
                    })}
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {LANGUAGES.map((l) => {
                      const active = language === l.key;
                      return (
                        <button
                          key={l.key}
                          onClick={() => setLanguage(l.key)}
                          className={`px-3 py-1 font-label text-[11px] uppercase tracking-widest rounded-full cursor-pointer transition-colors border ${
                            active
                              ? "bg-[#2b3437] text-white border-[#2b3437]"
                              : "bg-transparent text-[#586064] border-[#eaeff1] hover:border-[#2b3437] hover:text-[#2b3437]"
                          }`}
                        >
                          {l.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <button
                  onClick={handleRestyle}
                  disabled={!selected || restyling}
                  className="flex items-center gap-2 text-sm font-bold tracking-wide text-[#575e70] hover:text-[#4b5264] transition-colors disabled:opacity-40"
                >
                  {restyling ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                  {restyling ? "Restyling…" : "Restyle Tone"}
                </button>
              </div>
            </div>
          </section>

          {/* ── Section 3: Visual Treatment ───────────────────── */}
          <section className="space-y-10">
            <div className="flex items-center justify-between border-b border-[#eaeff1] pb-4">
              <h2 className="font-headline text-2xl font-bold">3. Visual Treatment</h2>
              <span className="px-2 py-1 bg-[#d3ceef] text-[#47445f] text-[10px] font-bold uppercase tracking-widest rounded">
                Beta
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] gap-10 items-start">
              {/* Preview — larger, sticky-ish on desktop */}
              <div className="aspect-[4/5] bg-[#eaeff1] rounded-3xl overflow-hidden relative shadow-[0_12px_32px_rgba(43,52,55,0.06)]">
                {activePreview ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={activePreview}
                    alt="Campaign preview"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[#586064] text-sm">
                    <ImageIcon size={56} />
                  </div>
                )}
                {generating && (
                  <div className="absolute inset-0 bg-black/30 flex items-center justify-center text-white">
                    <Loader2 size={40} className="animate-spin" />
                  </div>
                )}
              </div>

              {/* Controls column */}
              <div className="space-y-7">
                {/* Two upload boxes side-by-side */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  {/* Model photo */}
                  <div className="bg-[#f1f4f6] rounded-2xl p-6 ring-1 ring-black/5 space-y-4">
                    <div className="flex items-center justify-between">
                      <label className="block font-label text-[10px] uppercase tracking-widest text-[#586064] font-bold">
                        Model Photo
                      </label>
                      <span className="text-[10px] text-[#586064]">optional</span>
                    </div>
                    <label className="block cursor-pointer">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleModelPhotoChange}
                        className="hidden"
                      />
                      <div className="w-full aspect-square rounded-xl bg-white ring-1 ring-black/5 overflow-hidden flex items-center justify-center hover:ring-[#575e70]/40 transition-all">
                        {modelPreview ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={modelPreview} alt="Model" className="w-full h-full object-cover" />
                        ) : (
                          <div className="flex flex-col items-center gap-2 text-[#586064]">
                            <Upload size={22} />
                            <span className="text-xs font-medium">Upload model</span>
                          </div>
                        )}
                      </div>
                      <p className="text-[11px] text-[#586064] mt-3 leading-relaxed">
                        The AI places this person with the product in the scene.
                      </p>
                    </label>
                  </div>

                  {/* Background photo */}
                  <div className="bg-[#f1f4f6] rounded-2xl p-6 ring-1 ring-black/5 space-y-4">
                    <div className="flex items-center justify-between">
                      <label className="block font-label text-[10px] uppercase tracking-widest text-[#586064] font-bold">
                        Background
                      </label>
                      <span className="text-[10px] text-[#586064]">optional</span>
                    </div>
                    <label className="block cursor-pointer">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleBackgroundPhotoChange}
                        className="hidden"
                      />
                      <div className="w-full aspect-square rounded-xl bg-white ring-1 ring-black/5 overflow-hidden flex items-center justify-center hover:ring-[#575e70]/40 transition-all">
                        {backgroundPreview ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={backgroundPreview} alt="Background" className="w-full h-full object-cover" />
                        ) : (
                          <div className="flex flex-col items-center gap-2 text-[#586064]">
                            <Upload size={22} />
                            <span className="text-xs font-medium">Upload background</span>
                          </div>
                        )}
                      </div>
                      <p className="text-[11px] text-[#586064] mt-3 leading-relaxed">
                        Upload a custom backdrop, or pick a studio preset below.
                      </p>
                    </label>
                  </div>
                </div>

                {/* Image Model Selector */}
                <div className="space-y-3">
                  <label className="block font-label text-[10px] uppercase tracking-widest text-[#586064] font-bold">
                    AI Model
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {IMAGE_MODELS.map((m) => {
                      const active = imageModel === m.id;
                      return (
                        <button
                          key={m.id}
                          onClick={() => setImageModel(m.id)}
                          className={`px-3 py-1.5 font-label text-[11px] uppercase tracking-widest rounded-full cursor-pointer transition-colors border ${
                            active
                              ? "bg-[#2b3437] text-white border-[#2b3437]"
                              : "bg-transparent text-[#586064] border-[#eaeff1] hover:border-[#2b3437] hover:text-[#2b3437]"
                          }`}
                          title={m.desc}
                        >
                          {m.label}
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-[#586064]">
                    {IMAGE_MODELS.find((m) => m.id === imageModel)?.desc}
                  </p>
                </div>

                {/* Prompt Tones */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="block font-label text-[10px] uppercase tracking-widest text-[#586064] font-bold">
                      Prompt Tone
                    </label>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {PROMPT_TONES.map((t) => {
                      const active = promptTone === t.id;
                      return (
                        <button
                          key={t.id}
                          onClick={() => {
                            setPromptTone(t.id);
                            handleGeneratePrompt(t.id, true);
                          }}
                          disabled={generating || generatingPrompt || !selected}
                          className={`px-3 py-1 font-label text-[11px] uppercase tracking-widest rounded-full cursor-pointer transition-colors border disabled:opacity-40 ${
                            active
                              ? "bg-[#2b3437] text-white border-[#2b3437]"
                              : "bg-transparent text-[#586064] border-[#eaeff1] hover:border-[#2b3437] hover:text-[#2b3437]"
                          }`}
                        >
                          {t.label}
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-[#586064] mt-1">
                    Click a tone to auto-generate prompt + caption + image
                  </p>
                </div>

                {/* Prompt */}
                <div className="bg-[#f1f4f6] rounded-2xl p-6 ring-1 ring-black/5 focus-within:ring-[#575e70]/30 focus-within:bg-white transition-all">
                  <div className="flex items-center justify-between mb-3">
                    <label className="block font-label text-[10px] uppercase tracking-widest text-[#586064] font-bold">
                      Direction Prompt
                    </label>
                    <button
                      onClick={() => handleGeneratePrompt()}
                      disabled={generatingPrompt || !selected}
                      className="text-xs text-[#575e70] hover:text-[#2b3437] font-bold flex items-center gap-1 disabled:opacity-50"
                    >
                      {generatingPrompt ? <Loader2 size={12} className="animate-spin" /> : <Wand2 size={12} />}
                      AI Generate
                    </button>
                  </div>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Describe the scene, pose, lighting…"
                    className="w-full bg-transparent border-none focus:ring-0 focus:outline-none resize-none font-body text-sm text-[#2b3437] min-h-[120px]"
                  />
                </div>

                <button
                  onClick={handleGenerate}
                  disabled={!selected || generating}
                  className="w-full text-white font-label font-bold text-xs uppercase tracking-widest py-4 rounded-xl hover:-translate-y-0.5 transition-transform shadow-[0_8px_24px_rgba(87,94,112,0.2)] flex justify-center items-center gap-2 disabled:opacity-40 disabled:translate-y-0"
                  style={{ background: "linear-gradient(145deg, #575e70 0%, #4b5264 100%)" }}
                >
                  {generating ? <Loader2 size={16} className="animate-spin" /> : <Palette size={16} />}
                  {generating ? "Generating…" : "Generate Variation"}
                </button>

                {visualError && (
                  <div className="text-xs text-[#752121] bg-[#fe8983]/20 border border-[#fe8983]/40 rounded-lg px-3 py-2">
                    {visualError}
                  </div>
                )}

                {/* Variation strip */}
                {variations.length > 0 && (
                  <div className="flex gap-3 overflow-x-auto pb-2">
                    {variations.map((v, i) => {
                      const active = i === activeVariant;
                      return (
                        <button
                          key={v.image_url}
                          onClick={() => setActiveVariant(i)}
                          className={`w-20 h-20 rounded-xl shrink-0 overflow-hidden transition-all ${
                            active ? "ring-2 ring-[#575e70]" : "opacity-50 hover:opacity-100"
                          }`}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={v.image_url} alt={`Variation ${i + 1}`} className="w-full h-full object-cover" />
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </section>

          {/* ── Section 4: Review & Deploy ──────────────────── */}
          <section className="pt-12 border-t border-[#eaeff1] space-y-8">
            <div className="text-center space-y-2">
              <h2 className="font-headline text-3xl font-bold">Review & Deploy</h2>
              <p className="font-body text-[#586064] text-sm">
                Select channels to syndicate this campaign.
              </p>
            </div>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              {(["facebook", "instagram"] as CampaignChannel[]).map((ch) => {
                const on = channels[ch];
                return (
                  <label
                    key={ch}
                    className={`flex items-center gap-3 p-4 bg-white rounded-2xl cursor-pointer transition-shadow hover:shadow-md ring-1 ${
                      on ? "ring-[#575e70]/40" : "ring-black/5"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={(e) => setChannels((c) => ({ ...c, [ch]: e.target.checked }))}
                      className="text-[#575e70] focus:ring-[#575e70] rounded"
                    />
                    <span className="font-headline font-semibold capitalize">
                      {ch === "facebook" ? "Facebook Page" : "Instagram Feed"}
                    </span>
                  </label>
                );
              })}
            </div>

            {launchResult && (
              <div
                className={`max-w-md mx-auto text-sm px-4 py-3 rounded-xl ${
                  launchResult.ok
                    ? "bg-green-50 text-green-700 border border-green-200"
                    : "bg-[#fe8983]/15 text-[#752121] border border-[#fe8983]/40"
                }`}
              >
                {launchResult.ok ? (
                  <>Deployed to {launchResult.deployed.join(", ")}.</>
                ) : (
                  <>
                    {launchResult.deployed.length > 0 && (
                      <>Deployed: {launchResult.deployed.join(", ")}. </>
                    )}
                    Errors: {launchResult.failed.map((f) => `${f.channel}: ${f.error}`).join("; ")}
                  </>
                )}
              </div>
            )}

            <div className="flex justify-center pt-4">
              <button
                onClick={handleLaunch}
                disabled={launching || !selected?.image_path}
                className="text-white font-headline font-bold text-lg px-12 py-4 rounded-2xl hover:-translate-y-1 transition-transform shadow-[0_12px_32px_rgba(87,94,112,0.3)] flex items-center gap-3 disabled:opacity-40 disabled:translate-y-0"
                style={{ background: "linear-gradient(145deg, #575e70 0%, #4b5264 100%)" }}
              >
                {launching ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
                {launching ? "Launching…" : "Launch Campaign"}
              </button>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
