"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Package, BarChart3, Settings, Sparkles, ArrowLeft, RefreshCw } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import {
  fetchAnalyticsDashboard,
  ForecastPoint,
  ForecastRange,
  OverviewStats,
  TrendingProduct,
  LogisticsRow,
} from "@/lib/api";
import { SalesIndexCard } from "@/components/analytics/SalesIndexCard";
import { ForecastChart } from "@/components/analytics/ForecastChart";
import { TrendingCard } from "@/components/analytics/TrendingCard";
import { LogisticsTable } from "@/components/analytics/LogisticsTable";

export default function AnalyticsPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [trending, setTrending] = useState<TrendingProduct[]>([]);
  const [logistics, setLogistics] = useState<LogisticsRow[]>([]);
  const [forecastRange, setForecastRange] = useState<ForecastRange>("7d");
  const [forecastPoints, setForecastPoints] = useState<ForecastPoint[]>([]);
  const [forecastSplitIndex, setForecastSplitIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAnalyticsDashboard(forecastRange);
      setStats(data.stats);
      setTrending(data.products || []);
      setLogistics(data.rows || []);
      setForecastPoints(data.forecast?.points || []);
      setForecastSplitIndex(data.forecast?.historical_end_index ?? 0);
    } catch (e) {
      console.error("analytics load failed", e);
    } finally {
      setLoading(false);
    }
  }, [forecastRange]);

  useEffect(() => { loadAll(); }, [loadAll]);

  return (
    <div className="flex min-h-screen bg-background text-on-background font-body antialiased">
      <Sidebar />

      {/* Main */}
      <main className="flex-1 flex flex-col min-h-screen">
        <div className="flex-1 p-8 md:p-12 lg:p-16 max-w-7xl mx-auto w-full">
          {/* Hero */}
          <div className="mb-16 flex justify-between items-end gap-6">
            <div>
              <h2 className="font-headline text-5xl font-light tracking-tight text-on-background">Executive Overview</h2>
              <p className="font-body text-sm text-on-surface-variant mt-4 max-w-xl leading-relaxed">
                A high-level synthesis of current performance metrics, predictive demand modeling, and active logistical states.
              </p>
            </div>
            <button
              onClick={loadAll}
              className="bg-primary text-on-primary px-6 py-3 rounded font-label text-sm font-medium hover:bg-primary-dim transition-all duration-200 shadow-[0_4px_14px_0_rgba(43,52,55,0.06)] hover:-translate-y-0.5 inline-flex items-center gap-2"
            >
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {/* Bento */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-16">
            <SalesIndexCard
              todayRevenue={stats?.today_revenue ?? 0}
              yesterdayRevenue={stats?.yesterday_revenue ?? 0}
              deltaPct={stats?.day_delta_pct ?? 0}
            />
            <ForecastChart
              range={forecastRange}
              points={forecastPoints}
              splitIndex={forecastSplitIndex}
              loading={loading}
              onRangeChange={setForecastRange}
            />
          </div>

          {/* Summary strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-16">
            <StatTile label="Total Revenue" value={`Rs. ${(stats?.total_revenue ?? 0).toLocaleString()}`} />
            <StatTile label="Total Orders" value={String(stats?.total_orders ?? 0)} />
            <StatTile label="Customers" value={String(stats?.total_customers ?? 0)} />
            <StatTile label="Active SKUs" value={String(stats?.total_products ?? 0)} />
          </div>

          {/* Trending */}
          <div className="mb-16">
            <h3 className="font-headline text-2xl font-light text-on-background mb-8">Trending Collections</h3>
            {loading && trending.length === 0 ? (
              <div className="font-label text-xs uppercase tracking-widest text-on-surface-variant">Scoring demand…</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {trending.map((p) => (
                  <TrendingCard key={p.product_id} product={p} />
                ))}
              </div>
            )}
          </div>

          {/* Logistics */}
          <div>
            <h3 className="font-headline text-2xl font-light text-on-background mb-8">Active Logistics</h3>
            <LogisticsTable rows={logistics} />
          </div>
        </div>
      </main>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-container-lowest rounded-xl p-6">
      <div className="font-label text-[10px] uppercase tracking-widest text-on-surface-variant font-medium mb-2">{label}</div>
      <div className="font-headline text-3xl font-light tracking-tight text-on-background">{value}</div>
    </div>
  );
}
