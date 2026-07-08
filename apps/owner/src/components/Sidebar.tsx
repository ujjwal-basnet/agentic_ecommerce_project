"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Package, BarChart3, Sparkles, Settings, Lightbulb, Plus } from "lucide-react";

const NAV_ITEMS = [
  { href: "/",          icon: <Package  size={18} strokeWidth={1.8} />, label: "Inventory"  },
  { href: "/analytics", icon: <BarChart3 size={18} strokeWidth={1.8} />, label: "Analytics" },
  { href: "/workflow",  icon: <Sparkles  size={18} strokeWidth={1.8} />, label: "Workflow"  },
  { href: "#",          icon: <Settings  size={18} strokeWidth={1.8} />, label: "Settings"  },
];

interface SidebarProps {
  /** Render an optional bottom CTA (e.g. "New Entry" button on inventory page) */
  bottomCta?: React.ReactNode;
}

export function Sidebar({ bottomCta }: SidebarProps) {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <aside className="w-[220px] bg-white flex-shrink-0 flex flex-col border-r border-[#f0f0f5]">
      {/* ── Logo ─────────────────────────────────────────────── */}
      <div className="px-6 pt-7 pb-2">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#5B6278] to-[#7A8194] flex items-center justify-center">
            <Lightbulb size={15} className="text-white" />
          </div>
          <span className="font-headline font-extrabold text-[15px] tracking-tight text-[#1a1d23]">
            SmartShop
          </span>
        </div>
      </div>

      {/* ── Nav ──────────────────────────────────────────────── */}
      <nav className="flex-1 px-3 pt-6 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          const Wrapper = item.href === "#" ? "button" : Link;
          return (
            <Wrapper
              key={item.label}
              href={item.href as any}
              className={`group w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-[13.5px] font-semibold transition-all duration-200 ${
                active
                  ? "bg-[#E8EAF0] text-[#5C637A]"
                  : "text-[#7A8194] hover:bg-[#F0F1F5] hover:text-[#2F3545]"
              }`}
            >
              <span
                className={`transition-colors duration-200 ${
                  active ? "text-[#5C637A]" : "text-[#9ca3af] group-hover:text-[#7A8194]"
                }`}
              >
                {item.icon}
              </span>
              {item.label}
            </Wrapper>
          );
        })}
      </nav>

      {/* ── Bottom CTA ───────────────────────────────────────── */}
      {bottomCta && (
        <div className="px-3 pb-5 pt-2">
          <div className="border-t border-[#f0f0f5] pt-4">{bottomCta}</div>
        </div>
      )}
    </aside>
  );
}
