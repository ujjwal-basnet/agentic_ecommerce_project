"use client";

import { useMemo } from "react";
import { ForecastPoint, ForecastRange } from "@/lib/api";

const RANGES: ForecastRange[] = ["7d", "30d", "ytd"];

interface Props {
  range: ForecastRange;
  points: ForecastPoint[];
  splitIndex: number;
  loading: boolean;
  onRangeChange: (range: ForecastRange) => void;
}

export function ForecastChart({ range, points, splitIndex, loading, onRangeChange }: Props) {
  const { histPath, fwdPath, areaPath, minV, maxV } = useMemo(() => {
    if (points.length === 0) {
      return { histPath: "", fwdPath: "", areaPath: "", minV: 0, maxV: 0 };
    }
    const values = points.map((p) => p.value);
    const maxV = Math.max(...values, 1);
    const minV = Math.min(...values, 0);
    const span = Math.max(maxV - minV, 1);
    const n = points.length;
    const x = (i: number) => (i / (n - 1 || 1)) * 100;
    const y = (v: number) => 100 - ((v - minV) / span) * 90 - 5;

    // Historical: solid smooth curve via cubic through midpoints
    const histPts = points.slice(0, splitIndex + 1);
    const fwdPts = points.slice(splitIndex);

    const buildSmooth = (pts: ForecastPoint[], offset: number) => {
      if (pts.length === 0) return "";
      let d = `M${x(offset).toFixed(2)},${y(pts[0].value).toFixed(2)}`;
      for (let i = 1; i < pts.length; i++) {
        const gi = offset + i;
        const prevGi = offset + i - 1;
        const xc = (x(prevGi) + x(gi)) / 2;
        const yc = (y(pts[i - 1].value) + y(pts[i].value)) / 2;
        d += ` Q${x(prevGi).toFixed(2)},${y(pts[i - 1].value).toFixed(2)} ${xc.toFixed(2)},${yc.toFixed(2)}`;
      }
      d += ` T${x(offset + pts.length - 1).toFixed(2)},${y(pts[pts.length - 1].value).toFixed(2)}`;
      return d;
    };

    const histPath = buildSmooth(histPts, 0);
    const fwdPath = buildSmooth(fwdPts, splitIndex);

    const fullPath = buildSmooth(points, 0);
    const areaPath = `${fullPath} L100,100 L0,100 Z`;

    return { histPath, fwdPath, areaPath, minV, maxV };
  }, [points, splitIndex]);

  return (
    <div className="lg:col-span-8 bg-surface-container-lowest p-8 rounded-xl h-80 flex flex-col hover:shadow-[0_12px_32px_0_rgba(43,52,55,0.04)] transition-shadow duration-300">
      <div className="flex justify-between items-center mb-8">
        <span className="font-label text-xs uppercase tracking-widest text-on-surface-variant">
          Demand Forecasting
        </span>
        <div className="flex gap-2">
          {RANGES.map((r) => {
            const active = r === range;
            return (
              <button
                key={r}
                onClick={() => onRangeChange(r)}
                className={`px-3 py-1 font-label text-xs rounded-full uppercase tracking-widest transition-colors ${
                  active
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
                }`}
              >
                {r}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 relative w-full flex items-end">
        <div className="absolute inset-0 flex flex-col justify-between border-b border-l border-outline-variant/20 pb-6 pl-2">
          <div className="w-full border-t border-outline-variant/10 h-0" />
          <div className="w-full border-t border-outline-variant/10 h-0" />
          <div className="w-full border-t border-outline-variant/10 h-0" />
        </div>

        {loading && points.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-label text-xs uppercase tracking-widest text-on-surface-variant">
              Loading signals…
            </span>
          </div>
        ) : points.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="font-label text-xs uppercase tracking-widest text-on-surface-variant">
              No data yet
            </span>
          </div>
        ) : (
          <svg
            className="absolute inset-0 h-full w-full pt-4 pb-6 pl-2"
            preserveAspectRatio="none"
            viewBox="0 0 100 100"
          >
            <defs>
              <linearGradient id="forecast-gradient" x1="0%" x2="0%" y1="0%" y2="100%">
                <stop offset="0%" stopColor="#575e70" stopOpacity="0.35" />
                <stop offset="100%" stopColor="#575e70" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d={areaPath} fill="url(#forecast-gradient)" opacity="0.8" />
            <path
              d={histPath}
              fill="none"
              stroke="#575e70"
              strokeWidth="1.6"
              vectorEffect="non-scaling-stroke"
            />
            <path
              d={fwdPath}
              fill="none"
              stroke="#575e70"
              strokeWidth="1.4"
              strokeDasharray="2 2"
              opacity="0.7"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        )}
      </div>

      <div className="mt-3 flex justify-between items-center text-[10px] uppercase tracking-widest text-on-surface-variant font-label">
        <span>min {Math.round(minV)}</span>
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 bg-primary rounded" /> Actual
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-4 h-0.5 border-t border-dashed border-primary" /> Forecast
          </span>
        </span>
        <span>max {Math.round(maxV)}</span>
      </div>
    </div>
  );
}
