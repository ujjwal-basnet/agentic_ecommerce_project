"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { ArrowUp, Paperclip, ShoppingBag, Trash2 } from "lucide-react";
import { fetchSSE, fetchCart, clearChat, uploadPhoto } from "@/lib/api";
import { renderGenUI } from "@/components/genui/Registry";

interface Message {
  id: string;
  role: "user" | "assistant";
  text?: string;
  component?: string;
  data?: any;
  tool?: string;
  ts?: string;
}

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
  const [cartCount, setCartCount] = useState(0);
  const [userImagePath, setUserImagePath] = useState<string | null>(null);
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

  const sendMessage = useCallback(async (msg: string) => {
    if (!msg.trim() || loading) return;
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
        } else if (event.type === "cart_sync") {
          setCartCount(event.cart_count || 0);
          refreshCart();
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
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await uploadPhoto(sessionId.current, file);
      setUserImagePath(res.path);
      setMessages((prev) => [...prev, { id: genId(), role: "assistant", text: "Photo uploaded! You can now try on wearable products.", ts: timeNow() }]);
    } catch {
      setMessages((prev) => [...prev, { id: genId(), role: "assistant", text: "Failed to upload photo.", ts: timeNow() }]);
    }
    e.target.value = "";
  }

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      {/* ── Top Nav ── */}
      <header className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-xl shadow-sm shadow-surface-container-high/50">
        <div className="flex justify-between items-center w-full px-6 h-16 max-w-screen-2xl mx-auto">
          <div className="font-headline font-bold tracking-tighter text-xl text-on-surface">SMARTSHOP</div>
          <nav className="hidden md:flex items-center space-x-8 font-headline font-medium tracking-tight text-sm">
            <a className="text-on-surface border-b border-on-surface pb-1" href="#">Chat</a>
            <a className="text-outline hover:text-on-surface transition-colors" href="#">Collections</a>
            <a className="text-outline hover:text-on-surface transition-colors" href="#">Artisans</a>
          </nav>
          <div className="flex items-center space-x-3">
            <button onClick={handleClear} className="p-2 text-on-surface-variant hover:text-on-surface transition-colors active:scale-95" title="Clear chat">
              <Trash2 size={18} />
            </button>
            <button
              onClick={() => sendMessage("show my cart")}
              className="relative p-2 text-on-surface-variant hover:text-on-surface transition-colors active:scale-95"
              title="View cart"
            >
              <ShoppingBag size={18} />
              {cartCount > 0 && (
                <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-on-primary">{cartCount}</span>
              )}
            </button>
          </div>
        </div>
        <div className="bg-surface-container-high/30 h-px w-full" />
      </header>

      {/* ── Main Chat Canvas ── */}
      <main className="flex-grow pt-24 pb-36 px-4 md:px-8 max-w-4xl mx-auto w-full">
        {/* Welcome */}
        {messages.length === 0 && (
          <div className="text-center mb-16 mt-8">
            <span className="font-headline text-[10px] uppercase tracking-[0.2em] text-on-surface-variant font-bold">SmartShop Concierge</span>
            <h1 className="font-headline text-3xl md:text-4xl font-light tracking-tight mt-3 text-on-surface">Curated Assistant</h1>
            <p className="font-body text-sm text-on-surface-variant mt-4 max-w-md mx-auto leading-relaxed">
              Search products, get personalized recommendations, manage your cart, or try on wearables virtually.
            </p>
            <div className="flex flex-wrap gap-2 mt-8 justify-center">
              {["Show me red shirts", "Recommend something", "Weather in Kathmandu", "View my cart"].map((q) => (
                <button
                  key={q}
                  onClick={() => { setInput(q); inputRef.current?.focus(); }}
                  className="font-headline text-xs tracking-tight px-4 py-2.5 rounded-full bg-surface-container-lowest border border-outline-variant/10 text-on-surface-variant hover:text-on-surface hover:border-outline-variant/30 transition-all shadow-sm"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="space-y-8">
          {messages.map((msg) =>
            msg.role === "user" ? (
              <div key={msg.id} className="flex flex-col items-end space-y-1.5">
                <div className="max-w-[80%] px-5 py-3 bg-primary text-on-primary rounded-xl rounded-tr-none font-headline font-light text-sm shadow-sm">
                  {msg.text}
                </div>
                {msg.ts && <span className="font-label text-[9px] uppercase tracking-widest text-on-surface-variant px-1">{msg.ts}</span>}
              </div>
            ) : (
              <div key={msg.id} className="flex flex-col items-start space-y-2">
                {msg.text && (
                  <div className="max-w-[85%] px-5 py-3 bg-surface-container-lowest text-on-surface rounded-xl rounded-tl-none font-headline font-light text-sm border border-outline-variant/10 shadow-sm">
                    {msg.text}
                  </div>
                )}
                {msg.component && (
                  <div className="w-full">
                    {renderGenUI(msg.component, msg.data, sessionId.current, refreshCart, sendMessage)}
                  </div>
                )}
                <div className="flex items-center space-x-2 px-1">
                  <span className="w-1 h-1 rounded-full bg-primary/40" />
                  <span className="font-label text-[9px] uppercase tracking-widest text-on-surface-variant">SmartShop Concierge</span>
                </div>
              </div>
            )
          )}

          {loading && (
            <div className="flex flex-col items-start space-y-2">
              <div className="px-5 py-4 bg-surface-container-lowest rounded-xl rounded-tl-none border border-outline-variant/10 shadow-sm">
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 bg-outline-variant rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-outline-variant rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-outline-variant rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
              <div className="flex items-center space-x-2 px-1">
                <span className="w-1 h-1 rounded-full bg-primary/40" />
                <span className="font-label text-[9px] uppercase tracking-widest text-on-surface-variant">thinking...</span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </main>

      {/* ── Persistent Chat Input ── */}
      <div className="fixed bottom-0 left-0 w-full z-40">
        <div className="max-w-4xl mx-auto px-4 md:px-8 pb-8 pt-4 bg-gradient-to-t from-surface via-surface to-transparent">
          <form
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
            className="relative"
          >
            <div className="bg-surface-container-lowest border border-outline-variant/10 rounded-xl flex items-center px-4 py-3 shadow-[0_4px_24px_rgba(0,0,0,0.04)] focus-within:border-primary/20 transition-all">
              <label className="p-2 text-on-surface-variant hover:text-primary transition-colors cursor-pointer">
                <Paperclip size={18} />
                <input type="file" accept="image/*" className="hidden" onChange={handleUpload} />
              </label>
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Inquire about a piece..."
                className="flex-grow bg-transparent border-none focus:ring-0 focus:outline-none text-sm font-headline tracking-tight text-on-surface placeholder:text-outline-variant/50 px-3"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className="w-10 h-10 bg-primary text-on-primary rounded-lg flex items-center justify-center hover:bg-primary-dim transition-all shadow-md disabled:opacity-30 active:scale-95"
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </form>
          <p className="text-center mt-3 font-label text-[10px] text-on-surface-variant/60 tracking-tight">SmartShop AI responds instantly.</p>
        </div>
      </div>
    </div>
  );
}
