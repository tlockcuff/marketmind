"use client";

import type { Stats } from "@/lib/types";
import { SkeletonRows } from "@/components/ui/skeleton";

interface Props {
  stats: Stats | null;
}

function Row({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className={`text-sm font-medium ${className}`}>{value}</span>
    </div>
  );
}

export function StatsPanel({ stats }: Props) {
  if (!stats) {
    return (
      <div className="border border-border rounded-sm bg-card">
        <div className="panel-header"><span className="panel-title">STATS</span></div>
        <div className="px-3 py-2"><SkeletonRows rows={5} /></div>
      </div>
    );
  }

  const dtDisplay = stats.is_paper || stats.day_trades_remaining >= 100
    ? "unlimited"
    : `${stats.day_trades_remaining} left (${stats.day_trade_count} used)`;
  const dtColor = stats.is_paper || stats.day_trades_remaining >= 2
    ? ""
    : stats.day_trades_remaining === 1
    ? "text-yellow-400"
    : "text-red-400";

  return (
    <div className="border border-border rounded-sm bg-card">
      <div className="panel-header">
        <span className="panel-title">STATS</span>
      </div>
      <div className="px-3 py-2">
        <Row label="Positions" value={`${stats.position_count}/${stats.max_positions}`} />
        <Row label="Winners" value={String(stats.winners)} className="text-green-400" />
        <Row label="Losers" value={String(stats.losers)} className="text-red-400" />
        <Row label="Open Orders" value={String(stats.open_orders)} />
        <Row label="Day Trades" value={dtDisplay} className={dtColor} />
      </div>
    </div>
  );
}
