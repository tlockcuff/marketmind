"use client";

import { useEffect, useState, useCallback } from "react";
import { getApiUrl } from "@/lib/utils";
import { AppShell } from "@/components/layout/app-shell";
import { MetricsCards } from "@/components/analytics/metrics-cards";
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
    <AppShell currentTab="analytics">
      <div className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-foreground mb-2">Analytics</h1>
            <p className="text-sm text-muted-foreground">
              Performance metrics and trading insights
            </p>
          </div>
          <div className="flex items-center gap-1">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-3 py-1 text-xs font-medium rounded-sm transition-colors ${
                  range === r
                    ? "bg-[#ff9e2c] text-black"
                    : "bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="border border-red-500/30 bg-red-500/10 rounded-sm px-4 py-3 mb-6 text-red-400 text-sm">
            {error}
          </div>
        )}

        {loading && !data && (
          <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
            Loading analytics...
          </div>
        )}

        {data && (
          <div className="space-y-6">
            <MetricsCards metrics={data.metrics} />
            
            {/* Enhanced Equity Curve with Benchmarks */}
            <EquityCurveEnhanced range={range} />
            
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <CumulativePnlChart data={data.cumulative_pnl} />
              <WinLossHistogram trades={data.trades} />
            </div>
            
            {/* Strategy Performance Table */}
            <StrategyBreakdownTable range={range} />
            
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
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
    </AppShell>
  );
}
