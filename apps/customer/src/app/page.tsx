"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowUp, Paperclip, ShoppingBag, X, ChevronLeft, MoreHorizontal, Trash2, UserX, Mic, MicOff } from "lucide-react";
import { fetchSSE, fetchCart, clearChat, uploadPhoto, imageUrl, deleteAccount } from "@/lib/api";
import { renderGenUI } from "@/components/genui/Registry";
import OrderHistory from "@/components/genui/OrderHistory";

interface Message {
  id: string;
  role: "user" | "assistant";
  text?: string;
  component?: string;
  data?: any;
  tool?: string;
  ts?: string;
  image_path?: string;
}

type AppView = "chat" | "orders";

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

function getSessionId() {
  if (typeof window === "undefined") return "ssr";
  let sid = localStorage.getItem("smartshop_session");
  if (!sid) {
    sid = "sess_" + genId();
    localStorage.setItem("smartshop_session", sid);
  }
  return sid;
}

function timeNow() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  const [cartCount, setCartCount] = useState(0);
  const [userImagePath, setUserImagePath] = useState<string | null>(null);
  const [view, setView] = useState<AppView>("chat");
  const [menuOpen, setMenuOpen] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionId = useRef(getSessionId());

  const scrollToBottom = useCallback(() => {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 120);
  }, []);

  const refreshCart = useCallback(async () => {
    try {
      const data = await fetchCart(sessionId.current);
      setCartCount(data.count || 0);
    } catch {}
  }, []);

  useEffect(() => { refreshCart(); }, [refreshCart]);

  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = true;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = "en-US";
      
      recognitionRef.current.onresult = (e: any) => {
        let finalTranscript = "";
        for (let i = e.resultIndex; i < e.results.length; ++i) {
          if (e.results[i].isFinal) {
            finalTranscript += e.results[i][0].transcript;
          }
        }
        if (finalTranscript) {
          setInput((prev) => {
            const clean = finalTranscript.trim();
            return prev ? `${prev.trim()} ${clean}` : clean;
          });
        }
      };
      
      recognitionRef.current.onerror = (event: any) => {
        console.error("Speech recognition error", event);
        setIsListening(false);
        if (event.error === "not-allowed") {
          alert("Microphone permission was denied. Please allow microphone access in your browser settings to use voice input.");
        } else {
          alert(`Speech recognition error: ${event.error}. Please ensure your microphone is plugged in and active.`);
        }
      };
      recognitionRef.current.onend = () => setIsListening(false);
    }
  }, []);

  const toggleListening = () => {
    if (!recognitionRef.current) {
      alert("Speech recognition is not supported in this browser or over insecure HTTP. Please try using Google Chrome, Microsoft Edge, or Safari over a secure HTTPS connection.");
      return;
    }
    if (isListening) {
      recognitionRef.current.stop();
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (e: any) {
        console.error("Speech recognition failed to start", e);
        alert(`Failed to start speech recognition: ${e.message || e}`);
      }
    }
  };

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = () => setMenuOpen(false);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [menuOpen]);

  const updateMessageData = useCallback((msgId: string, patch: any) => {
    setMessages((prev) =>
      prev.map((m) =>
        m.id === msgId ? { ...m, data: { ...(typeof m.data === "object" && m.data ? m.data : {}), ...patch } } : m
      )
    );
  }, []);

  const handleTryOnResult = useCallback((imagePath: string, productName: string) => {
    setMessages((prev) => [
      ...prev,
      { id: genId(), role: "assistant", text: `Here's how ${productName} looks on you!`, image_path: imagePath, ts: timeNow() },
    ]);
    scrollToBottom();
  }, [scrollToBottom]);

  const sendMessage = useCallback(async (msg: string) => {
    if (!msg.trim() || loading) return;
    setView("chat");
    const userMsg: Message = { id: genId(), role: "user", text: msg, ts: timeNow() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    scrollToBottom();

    const assistantId = genId();

    await fetchSSE(
      msg,
      sessionId.current,
      userImagePath,
      (event) => {
        if (event.type === "text") {
          setMessages((prev) => {
            const existing = prev.find((m) => m.id === assistantId);
            if (existing) {
              return prev.map((m) => (m.id === assistantId ? { ...m, text: event.content } : m));
            }
            return [...prev, { id: assistantId, role: "assistant", text: event.content, ts: timeNow() }];
          });
          scrollToBottom();
        } else if (event.type === "tool_result") {
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "assistant", component: event.component, data: event.data, tool: event.tool, ts: timeNow() },
          ]);
          scrollToBottom();
        } else if (event.type === "image") {
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "assistant", image_path: event.image_path, ts: timeNow() },
          ]);
          scrollToBottom();
        } else if (event.type === "cart_sync") {
          setCartCount(event.cart_count || 0);
          refreshCart();
        } else if (event.type === "error") {
          setMessages((prev) => [...prev, { id: genId(), role: "assistant", text: event.content || "Something went wrong.", ts: timeNow() }]);
          scrollToBottom();
        }
      },
      () => setLoading(false),
      (err) => {
        setMessages((prev) => [...prev, { id: genId(), role: "assistant", text: `Connection error: ${err}`, ts: timeNow() }]);
        setLoading(false);
      }
    );
  }, [loading, userImagePath, refreshCart, scrollToBottom]);

  async function handleSend() {
    const msg = input.trim();
    if (!msg) return;
    setInput("");
    sendMessage(msg);
  }

  async function handleClear() {
    await clearChat(sessionId.current);
    setMessages([]);
    setMenuOpen(false);
  }

  async function handleDeleteAccount() {
    const ok = window.confirm("This clears chat, cart, and orders for this browser session. It does not delete the admin login.");
    if (!ok) return;
    setMenuOpen(false);
    try {
      await deleteAccount(sessionId.current);
      localStorage.removeItem("smartshop_user");
      localStorage.removeItem("smartshop_session");
      window.location.reload();
    } catch {
      setMessages((prev) => [...prev, { id: genId(), role: "assistant", text: "Account deletion failed.", ts: timeNow() }]);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await uploadPhoto(sessionId.current, file);
      setUserImagePath(res.path);
      setMessages((prev) => [...prev, { id: genId(), role: "assistant", text: "Photo uploaded. You can now try on wearable products.", ts: timeNow() }]);
    } catch {
      setMessages((prev) => [...prev, { id: genId(), role: "assistant", text: "Upload failed. Please try again.", ts: timeNow() }]);
    }
    e.target.value = "";
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#fafafa]">
      {/* ── Navbar ── */}
      <header className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-xl border-b border-[#e5e5ea]">
        <div className="flex items-center justify-between w-full px-5 h-12 max-w-3xl mx-auto">
          {/* Left: Logo */}
          <button onClick={() => setView("chat")} className="font-headline font-bold text-[15px] tracking-tight text-[#1d1d1f]">
            SmartShop
          </button>

          {/* Center: Tabs */}
          <div className="flex items-center gap-1 bg-[#f5f5f7] rounded-full p-0.5">
            <button
              onClick={() => setView("chat")}
              className={`px-4 py-1 rounded-full text-[12px] font-headline font-semibold transition-all ${
                view === "chat" ? "bg-white text-[#1d1d1f] shadow-subtle" : "text-[#86868b] hover:text-[#1d1d1f]"
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => setView("orders")}
              className={`px-4 py-1 rounded-full text-[12px] font-headline font-semibold transition-all ${
                view === "orders" ? "bg-white text-[#1d1d1f] shadow-subtle" : "text-[#86868b] hover:text-[#1d1d1f]"
              }`}
            >
              Orders
            </button>
          </div>

          {/* Right: Cart + Menu */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => { setView("chat"); sendMessage("show my cart"); }}
              className="relative p-1.5 rounded-lg text-[#86868b] hover:text-[#1d1d1f] transition-colors"
              title="Cart"
            >
              <ShoppingBag size={17} />
              {cartCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-[#1d1d1f] text-white text-[9px] font-bold">
                  {cartCount > 9 ? "9+" : cartCount}
                </span>
              )}
            </button>

            <div className="relative">
              <button
                onClick={(e) => { e.stopPropagation(); setMenuOpen(!menuOpen); }}
                className="p-1.5 rounded-lg text-[#86868b] hover:text-[#1d1d1f] transition-colors"
              >
                <MoreHorizontal size={17} />
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-full mt-1 w-44 bg-white rounded-xl shadow-floating border border-[#e5e5ea] overflow-hidden z-50">
                  <button onClick={handleClear} className="flex items-center gap-2.5 w-full px-3.5 py-2.5 text-[13px] text-[#1d1d1f] hover:bg-[#f5f5f7] transition-colors font-body">
                    <Trash2 size={14} className="text-[#86868b]" />
                    Clear chat
                  </button>
                  <div className="h-px bg-[#e5e5ea] mx-3" />
                  <button onClick={handleDeleteAccount} className="flex items-center gap-2.5 w-full px-3.5 py-2.5 text-[13px] text-[#ff3b30] hover:bg-[#fff2f0] transition-colors font-body">
                    <UserX size={14} />
                    Reset session
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ── Orders View ── */}
      {view === "orders" ? (
        <main className="flex-grow pt-16 pb-8 px-4 max-w-3xl mx-auto w-full">
          <button
            onClick={() => setView("chat")}
            className="flex items-center gap-1 text-[13px] text-[#86868b] hover:text-[#1d1d1f] transition-colors mb-5 font-body"
          >
            <ChevronLeft size={14} />
            Back to chat
          </button>
          <OrderHistory sessionId={sessionId.current} />
        </main>
      ) : (
        /* ── Chat View ── */
        <>
          <main className="flex-grow pt-12 pb-28 px-4 max-w-3xl mx-auto w-full">
            {/* Welcome */}
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center min-h-[calc(100vh-160px)] text-center px-4 fade-in">
                <h1 className="font-headline font-semibold text-[28px] tracking-tight text-[#1d1d1f] leading-tight mb-2">
                  Hi, how can I help?
                </h1>
                <p className="text-[14px] text-[#86868b] max-w-sm leading-relaxed mb-8 font-body">
                  Search products, get recommendations, manage your cart, or try on clothes virtually.
                </p>
                <div className="flex flex-wrap gap-2 justify-center max-w-md">
                  {["Show me shirts", "Recommend something", "What laptops do you have?", "View my cart"].map((q) => (
                    <button
                      key={q}
                      onClick={() => sendMessage(q)}
                      className="px-4 py-2 rounded-full bg-white border border-[#e5e5ea] text-[13px] font-body text-[#1d1d1f] hover:bg-[#f5f5f7] hover:border-[#d1d1d6] transition-all shadow-subtle"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Messages */}
            <div className="space-y-5 pt-4">
              {messages.map((msg) =>
                msg.role === "user" ? (
                  <div key={msg.id} className="flex justify-end fade-in">
                    <div className="max-w-[78%]">
                      <div className="bg-[#1d1d1f] text-white px-4 py-2.5 rounded-[18px] rounded-tr-[4px] text-[14px] font-body">
                        {msg.text}
                      </div>
                      {msg.ts && <p className="text-[10px] text-[#86868b] mt-1 text-right font-label">{msg.ts}</p>}
                    </div>
                  </div>
                ) : (
                  <div key={msg.id} className="flex flex-col items-start gap-2 fade-in">
                    {msg.text && (
                      <div className="max-w-[82%]">
                        <div className="bg-[#f5f5f7] text-[#1d1d1f] px-4 py-3 rounded-[18px] rounded-tl-[4px] text-[14px] font-body leading-relaxed">
                          {msg.text}
                        </div>
                        {msg.ts && (
                          <p className="text-[10px] text-[#86868b] mt-1 font-label">
                            {msg.ts}
                          </p>
                        )}
                      </div>
                    )}
                    {msg.image_path && (
                      <div className="max-w-[82%]">
                        <img
                          src={imageUrl(msg.image_path)}
                          alt=""
                          onError={(e) => { e.currentTarget.style.display = "none"; }}
                          className="rounded-2xl shadow-card max-h-[360px] object-contain"
                        />
                      </div>
                    )}
                    {msg.component && (
                      <div className="w-full">
                        {renderGenUI(
                          msg.component, msg.data, sessionId.current,
                          refreshCart, sendMessage,
                          (orderResult: any) => updateMessageData(msg.id, { __orderDone: orderResult }),
                          handleTryOnResult
                        )}
                      </div>
                    )}
                  </div>
                )
              )}

              {/* Typing */}
              {loading && (
                <div className="flex items-start fade-in">
                  <div className="bg-[#f5f5f7] px-5 py-3.5 rounded-[18px] rounded-tl-[4px]">
                    <div className="flex gap-1.5">
                      <span className="w-[6px] h-[6px] rounded-full bg-[#86868b] dot-pulse" style={{ animationDelay: "0ms" }} />
                      <span className="w-[6px] h-[6px] rounded-full bg-[#86868b] dot-pulse" style={{ animationDelay: "200ms" }} />
                      <span className="w-[6px] h-[6px] rounded-full bg-[#86868b] dot-pulse" style={{ animationDelay: "400ms" }} />
                    </div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          </main>

          {/* ── Input bar ── */}
          <div className="fixed bottom-0 left-0 w-full z-40">
            <div className="max-w-3xl mx-auto px-4 pb-4 pt-3 bg-gradient-to-t from-[#fafafa] via-[#fafafa]/95 to-transparent">
              <form onSubmit={(e) => { e.preventDefault(); handleSend(); }}>
                <div className="bg-white rounded-2xl border border-[#e5e5ea] flex items-center gap-1 px-2 py-1.5 shadow-card focus-within:border-[#d1d1d6] focus-within:shadow-card-hover transition-all">
                  <label className="flex-shrink-0 w-8 h-8 flex items-center justify-center text-[#86868b] hover:text-[#1d1d1f] rounded-lg transition-colors cursor-pointer" title="Upload photo">
                    <Paperclip size={15} />
                    <input type="file" accept="image/*" className="hidden" onChange={handleUpload} />
                  </label>

                  <button
                    type="button"
                    onClick={toggleListening}
                    className={`flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg transition-colors ${
                      isListening ? "text-[#ff3b30] bg-[#ff3b30]/10" : "text-[#86868b] hover:text-[#1d1d1f]"
                    }`}
                    title="Voice input"
                  >
                    {isListening ? <MicOff size={15} /> : <Mic size={15} />}
                  </button>

                  {userImagePath && (
                    <div className="flex-shrink-0 flex items-center gap-1 bg-[#f5f5f7] text-[#6e6e73] px-2 py-0.5 rounded-md">
                      <span className="text-[10px] font-body font-medium">Photo</span>
                      <button type="button" onClick={() => setUserImagePath(null)} className="hover:text-[#ff3b30] transition-colors">
                        <X size={10} />
                      </button>
                    </div>
                  )}

                  <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Message..."
                    className="flex-grow bg-transparent border-none focus:ring-0 focus:outline-none text-[14px] font-body text-[#1d1d1f] placeholder:text-[#c7c7cc] py-1 min-w-0"
                    disabled={loading}
                  />

                  <button
                    type="submit"
                    disabled={loading || !input.trim()}
                    className="flex-shrink-0 w-8 h-8 bg-[#1d1d1f] text-white rounded-xl flex items-center justify-center transition-all active:scale-95 disabled:opacity-20"
                  >
                    <ArrowUp size={15} />
                  </button>
                </div>
              </form>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
