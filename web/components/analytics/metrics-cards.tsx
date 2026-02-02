"use client";

import type { AnalyticsMetrics } from "@/lib/types";

interface Props {
  metrics: AnalyticsMetrics;
}

function Card({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="border border-border rounded-sm bg-card px-4 py-3">
      <div className="text-[11px] text-muted-foreground uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-lg font-bold ${color ?? "text-foreground"}`}>{value}</div>
    </div>
  );
}

function fmt(n: number): string {
  return n >= 0 ? `$${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : `-$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
}

export function MetricsCards({ metrics }: Props) {
  const pnlColor = metrics.total_pnl >= 0 ? "pl-positive" : "pl-negative";
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <Card label="Total P/L" value={fmt(metrics.total_pnl)} color={pnlColor} />
      <Card label="Win Rate" value={`${metrics.win_rate}%`} color={metrics.win_rate >= 50 ? "text-green-400" : "text-red-400"} />
      <Card label="Profit Factor" value={String(metrics.profit_factor)} color={metrics.profit_factor >= 1 ? "text-green-400" : "text-red-400"} />
      <Card label="Sharpe Ratio" value={String(metrics.sharpe_ratio)} color={metrics.sharpe_ratio >= 1 ? "text-green-400" : "text-yellow-400"} />
      <Card label="Max Drawdown" value={`${metrics.max_drawdown}%`} color="text-red-400" />
      <Card label="Total Trades" value={`${metrics.total_trades} (${metrics.win_count}W / ${metrics.loss_count}L)`} />
      <Card label="Avg Win" value={fmt(metrics.avg_win)} color="text-green-400" />
      <Card label="Avg Loss" value={fmt(metrics.avg_loss)} color="text-red-400" />
      <Card label="Best Trade" value={fmt(metrics.best_trade)} color="text-green-400" />
      <Card label="Worst Trade" value={fmt(metrics.worst_trade)} color="text-red-400" />
    </div>
  );
}
