"use client";

import { useEffect, useState } from "react";
import { getApiUrl } from "@/lib/utils";
import type { TradeAnalysisData } from "@/lib/types";

interface Props {
  range: string;
}

export function TradeAnalysis({ range }: Props) {
  const [data, setData] = useState<TradeAnalysisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${getApiUrl()}/api/analytics/trade-analysis?range=${range}`);
        const json = await res.json();
        if (json.error) {
          setError(json.error);
        } else {
          setData(json);
        }
      } catch (e: any) {
        setError(e.message ?? "Failed to fetch trade analysis");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [range]);

  if (loading) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Trade Analysis</h3>
        <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
          Loading trade analysis...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Trade Analysis</h3>
        <div className="text-red-400 text-sm">{error}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Trade Analysis</h3>
        <div className="text-muted-foreground text-sm">No trade data available</div>
      </div>
    );
  }

  const formatPnL = (pnl: number) => {
    const abs = Math.abs(pnl);
    const sign = pnl >= 0 ? "$" : "-$";
    return `${sign}${abs.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
  };

  const formatHours = (hours: number) => {
    if (hours < 1) return `${Math.round(hours * 60)}m`;
    if (hours < 24) return `${hours.toFixed(1)}h`;
    return `${(hours / 24).toFixed(1)}d`;
  };

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return "—";
    const date = new Date(dateStr);
    return date.toLocaleString(undefined, { 
      month: "short", 
      day: "numeric", 
      hour: "2-digit", 
      minute: "2-digit" 
    });
  };

  return (
    <div className="space-y-4">
      {/* Key Metrics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="border border-border rounded-sm bg-card px-3 py-2">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
            Avg Hold Time
          </div>
          <div className="text-sm font-bold text-foreground">
            {formatHours(data.hold_duration_analysis.avg_duration_hours)}
          </div>
        </div>
        
        <div className="border border-border rounded-sm bg-card px-3 py-2">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
            Win Hold Time
          </div>
          <div className="text-sm font-bold text-green-400">
            {formatHours(data.hold_duration_analysis.avg_win_duration_hours)}
          </div>
        </div>
        
        <div className="border border-border rounded-sm bg-card px-3 py-2">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
            Loss Hold Time
          </div>
          <div className="text-sm font-bold text-red-400">
            {formatHours(data.hold_duration_analysis.avg_loss_duration_hours)}
          </div>
        </div>
        
        <div className="border border-border rounded-sm bg-card px-3 py-2">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
            Recent Performance
          </div>
          <div className={`text-sm font-bold ${
            data.recent_performance.last_10_trades_pnl >= 0 ? "pl-positive" : "pl-negative"
          }`}>
            {formatPnL(data.recent_performance.last_10_trades_pnl)}
          </div>
          <div className="text-[10px] text-muted-foreground">
            {data.recent_performance.last_10_win_rate}% win (last {data.recent_performance.last_10_count})
          </div>
        </div>
      </div>

      {/* Best/Worst Trades */}
      {(data.best_trade || data.worst_trade) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {data.best_trade && (
            <div className="border border-green-500/30 rounded-sm bg-card p-3">
              <h4 className="text-xs font-medium text-green-400 mb-2">🏆 Best Trade</h4>
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <span className="font-mono text-sm">{data.best_trade.symbol}</span>
                  <span className="text-xs text-muted-foreground">
                    {data.best_trade.strategy_tag?.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="text-green-400 font-bold">{formatPnL(data.best_trade.pnl)}</div>
                <div className="text-[10px] text-muted-foreground space-y-0.5">
                  <div>Entry: ${data.best_trade.entry_price?.toFixed(2)} → Exit: ${data.best_trade.exit_price?.toFixed(2)}</div>
                  <div>Duration: {data.best_trade.hold_duration_hours ? formatHours(data.best_trade.hold_duration_hours) : "—"}</div>
                  <div>Closed: {formatDateTime(data.best_trade.exit_time)}</div>
                </div>
              </div>
            </div>
          )}
          
          {data.worst_trade && (
            <div className="border border-red-500/30 rounded-sm bg-card p-3">
              <h4 className="text-xs font-medium text-red-400 mb-2">📉 Worst Trade</h4>
              <div className="space-y-1">
                <div className="flex justify-between items-center">
                  <span className="font-mono text-sm">{data.worst_trade.symbol}</span>
                  <span className="text-xs text-muted-foreground">
                    {data.worst_trade.strategy_tag?.replace(/_/g, " ")}
                  </span>
                </div>
                <div className="text-red-400 font-bold">{formatPnL(data.worst_trade.pnl)}</div>
                <div className="text-[10px] text-muted-foreground space-y-0.5">
                  <div>Entry: ${data.worst_trade.entry_price?.toFixed(2)} → Exit: ${data.worst_trade.exit_price?.toFixed(2)}</div>
                  <div>Duration: {data.worst_trade.hold_duration_hours ? formatHours(data.worst_trade.hold_duration_hours) : "—"}</div>
                  <div>Closed: {formatDateTime(data.worst_trade.exit_time)}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Recent Trades Table */}
      <div className="border border-border rounded-sm bg-card p-4">
        <h4 className="text-sm font-medium mb-3">Recent Trades</h4>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-2 text-muted-foreground font-medium">Symbol</th>
                <th className="text-left py-2 px-2 text-muted-foreground font-medium">Strategy</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Entry</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Exit</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">P/L</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Hold</th>
                <th className="text-right py-2 px-2 text-muted-foreground font-medium">Exit Time</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_trades.slice(0, 15).map((trade, i) => (
                <tr key={i} className={i % 2 === 0 ? "bg-muted/30" : ""}>
                  <td className="py-2 px-2 font-mono font-medium">{trade.symbol}</td>
                  <td className="py-2 px-2 text-muted-foreground">
                    {trade.strategy_tag?.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()) || "—"}
                  </td>
                  <td className="text-right py-2 px-2">${trade.entry_price?.toFixed(2)}</td>
                  <td className="text-right py-2 px-2">${trade.exit_price?.toFixed(2)}</td>
                  <td className={`text-right py-2 px-2 font-medium ${
                    trade.pnl >= 0 ? "pl-positive" : "pl-negative"
                  }`}>
                    {formatPnL(trade.pnl)}
                  </td>
                  <td className="text-right py-2 px-2 text-muted-foreground">
                    {trade.hold_duration_hours ? formatHours(trade.hold_duration_hours) : "—"}
                  </td>
                  <td className="text-right py-2 px-2 text-muted-foreground">
                    {formatDateTime(trade.exit_time)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}