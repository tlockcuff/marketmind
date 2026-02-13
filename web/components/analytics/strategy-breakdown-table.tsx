"use client";

import { useEffect, useState } from "react";
import { getApiUrl } from "@/lib/utils";
import type { StrategyBreakdownData } from "@/lib/types";

interface Props {
  range: string;
}

export function StrategyBreakdownTable({ range }: Props) {
  const [data, setData] = useState<StrategyBreakdownData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${getApiUrl()}/api/analytics/strategy-breakdown?range=${range}`);
        const json = await res.json();
        if (json.error) {
          setError(json.error);
        } else {
          setData(json);
        }
      } catch (e: any) {
        setError(e.message ?? "Failed to fetch strategy breakdown");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [range]);

  if (loading) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Strategy Performance</h3>
        <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
          Loading strategy breakdown...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Strategy Performance</h3>
        <div className="text-red-400 text-sm">{error}</div>
      </div>
    );
  }

  if (!data?.strategy_breakdown?.length) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Strategy Performance</h3>
        <div className="text-muted-foreground text-sm">No strategy data available</div>
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

  return (
    <div className="border border-border rounded-sm bg-card p-4">
      <h3 className="text-sm font-medium mb-3">Strategy Performance</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-2 px-2 text-muted-foreground font-medium">Strategy</th>
              <th className="text-right py-2 px-2 text-muted-foreground font-medium">Trades</th>
              <th className="text-right py-2 px-2 text-muted-foreground font-medium">Win Rate</th>
              <th className="text-right py-2 px-2 text-muted-foreground font-medium">P/L</th>
              <th className="text-right py-2 px-2 text-muted-foreground font-medium">Avg P/L</th>
              <th className="text-right py-2 px-2 text-muted-foreground font-medium">PF</th>
              <th className="text-right py-2 px-2 text-muted-foreground font-medium">Avg Hold</th>
              <th className="text-right py-2 px-2 text-muted-foreground font-medium">Score</th>
            </tr>
          </thead>
          <tbody>
            {data.strategy_breakdown.map((strategy, i) => (
              <tr key={strategy.strategy} className={i % 2 === 0 ? "bg-muted/30" : ""}>
                <td className="py-2 px-2 font-medium text-foreground">
                  {strategy.strategy.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                </td>
                <td className="text-right py-2 px-2">
                  {strategy.trades}
                  <span className="text-muted-foreground ml-1">
                    ({strategy.wins}W/{strategy.losses}L)
                  </span>
                </td>
                <td className={`text-right py-2 px-2 ${
                  strategy.win_rate >= 60 ? "text-green-400" :
                  strategy.win_rate >= 40 ? "text-yellow-400" : "text-red-400"
                }`}>
                  {strategy.win_rate}%
                </td>
                <td className={`text-right py-2 px-2 font-medium ${
                  strategy.total_pnl >= 0 ? "pl-positive" : "pl-negative"
                }`}>
                  {formatPnL(strategy.total_pnl)}
                </td>
                <td className={`text-right py-2 px-2 ${
                  strategy.avg_pnl >= 0 ? "text-green-400" : "text-red-400"
                }`}>
                  {formatPnL(strategy.avg_pnl)}
                </td>
                <td className={`text-right py-2 px-2 ${
                  Number(strategy.profit_factor) >= 1.5 ? "text-green-400" :
                  Number(strategy.profit_factor) >= 1.0 ? "text-yellow-400" : "text-red-400"
                }`}>
                  {strategy.profit_factor}
                </td>
                <td className="text-right py-2 px-2 text-muted-foreground">
                  {formatHours(strategy.avg_hold_hours)}
                </td>
                <td className="text-right py-2 px-2 text-muted-foreground">
                  {strategy.avg_score}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}