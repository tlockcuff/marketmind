"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { getApiUrl } from "@/lib/utils";
import { MetricsCards } from "@/components/analytics/metrics-cards";
import { EquityCurveChart } from "@/components/analytics/equity-curve";
import { EquityCurveEnhanced } from "@/components/analytics/equity-curve-enhanced";
import { CumulativePnlChart } from "@/components/analytics/cumulative-pnl";
import { WinLossHistogram } from "@/components/analytics/win-loss-histogram";
import { SectorBreakdown } from "@/components/analytics/sector-breakdown";
import { StrategyBreakdownTable } from "@/components/analytics/strategy-breakdown-table";
import { TradeAnalysis } from "@/components/analytics/trade-analysis";
import type { AnalyticsData } from "@/lib/types";

const RANGES = ["1W", "1M", "3M", "ALL"] as const;
type Range = (typeof RANGES)[number];

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [range, setRange] = useState<Range>("ALL");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (r: Range) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${getApiUrl()}/api/analytics?range=${r}`);
      const json = await res.json();
      if (json.error) {
        setError(json.error);
      } else {
        setData(json);
      }
    } catch (e: any) {
      setError(e.message ?? "Failed to fetch analytics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(range);
  }, [range, fetchData]);

  return (
    <div className="min-h-screen bg-background text-foreground p-4">
      {/* Top bar */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-[#ff9e2c] font-bold text-sm tracking-wider hover:opacity-80">
            MARKETMIND
          </Link>
          <span className="text-[#3a3a48]">|</span>
          <span className="text-[12px] font-bold text-foreground uppercase tracking-wider">Analytics</span>
        </div>
        <div className="flex items-center gap-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 text-xs font-medium rounded-sm transition-colors ${
                range === r
                  ? "bg-[#ff9e2c] text-black"
                  : "bg-[#1a1a24] text-muted-foreground hover:text-foreground hover:bg-[#252530]"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="border border-red-500/30 bg-red-500/10 rounded-sm px-4 py-3 mb-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading && !data && (
        <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
          Loading analytics...
        </div>
      )}

      {data && (
        <div className="space-y-4">
          <MetricsCards metrics={data.metrics} />
          
          {/* Enhanced Equity Curve with Benchmarks */}
          <EquityCurveEnhanced range={range} />
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CumulativePnlChart data={data.cumulative_pnl} />
            <WinLossHistogram trades={data.trades} />
          </div>
          
          {/* Strategy Performance Table */}
          <StrategyBreakdownTable range={range} />
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <SectorBreakdown data={data.sector_breakdown} />
            <div className="border border-border rounded-sm bg-card p-4">
              <h3 className="text-sm font-medium mb-3">Strategy Distribution</h3>
              {data.strategy_breakdown?.length ? (
                <div className="space-y-2">
                  {data.strategy_breakdown.map((strategy, i) => (
                    <div key={strategy.strategy} className="flex justify-between items-center text-sm">
                      <span className="text-foreground">
                        {strategy.strategy.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                      </span>
                      <div className="text-right">
                        <span className={`font-medium ${
                          strategy.pnl >= 0 ? "text-green-400" : "text-red-400"
                        }`}>
                          {strategy.pnl >= 0 ? "$" : "-$"}{Math.abs(strategy.pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </span>
                        <span className="text-muted-foreground text-xs ml-2">
                          ({strategy.trades} trades)
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-muted-foreground text-sm">No strategy data available</div>
              )}
            </div>
          </div>
          
          {/* Trade Analysis Section */}
          <TradeAnalysis range={range} />
        </div>
      )}
    </div>
  );
}
