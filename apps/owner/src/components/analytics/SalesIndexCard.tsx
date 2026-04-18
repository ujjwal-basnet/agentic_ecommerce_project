import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface Props {
  todayRevenue: number;
  yesterdayRevenue: number;
  deltaPct: number;
}

export function SalesIndexCard({ todayRevenue, yesterdayRevenue, deltaPct }: Props) {
  const positive = deltaPct > 0;
  const negative = deltaPct < 0;
  const Icon = positive ? TrendingUp : negative ? TrendingDown : Minus;
  const toneClass = positive ? "text-primary" : negative ? "text-on-error-container" : "text-on-surface-variant";
  const sign = positive ? "+" : "";

  return (
    <div className="lg:col-span-4 bg-surface-container-lowest p-8 rounded-xl relative overflow-hidden flex flex-col justify-between h-80 group hover:shadow-[0_12px_32px_0_rgba(43,52,55,0.04)] transition-shadow duration-300">
      <div className="z-10">
        <span className="font-label text-xs uppercase tracking-widest text-on-surface-variant">
          AI Sales Index
        </span>
        <div className="mt-4 flex items-baseline gap-2">
          <span className={`font-headline text-7xl font-light tracking-tighter ${toneClass}`}>
            {sign}{deltaPct.toFixed(1)}%
          </span>
          <Icon size={20} className={toneClass} />
        </div>
        <p className="font-body text-sm text-on-surface-variant mt-4 leading-relaxed">
          vs yesterday — today&apos;s revenue compared to the previous day.
        </p>
      </div>

      <div className="z-10 grid grid-cols-2 gap-4 mt-6">
        <div>
          <div className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Today</div>
          <div className="font-headline text-xl font-light text-on-background">
            Rs. {todayRevenue.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant mb-1">Yesterday</div>
          <div className="font-headline text-xl font-light text-on-surface-variant">
            Rs. {yesterdayRevenue.toLocaleString()}
          </div>
        </div>
      </div>

      <div className="absolute -bottom-10 -right-10 w-48 h-48 bg-surface-container-low rounded-full blur-3xl opacity-50 group-hover:opacity-70 transition-opacity" />
    </div>
  );
}
