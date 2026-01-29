"use client";

import type { ApiUsage } from "@/lib/types";
import { SkeletonRows } from "@/components/ui/skeleton";

interface Props {
  usage: ApiUsage | null;
}

function Row({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className={`text-sm font-medium ${className}`}>{value}</span>
    </div>
  );
}

export function ApiUsagePanel({ usage }: Props) {
  if (!usage) {
    return (
      <div className="border border-border rounded-sm bg-card">
        <div className="panel-header"><span className="panel-title">GROK API</span></div>
        <div className="px-3 py-2"><SkeletonRows rows={5} /></div>
      </div>
    );
  }

  return (
    <div className="border border-border rounded-sm bg-card">
      <div className="panel-header">
        <span className="panel-title">GROK API</span>
      </div>
      <div className="px-3 py-2">
        <div className="text-xs font-bold text-foreground mb-0.5">Today</div>
        <Row label="Requests" value={String(usage.today.requests)} />
        <Row label="Signals" value={String(usage.today.signals)} />
        <Row label="Cost" value={`$${usage.today.cost.toFixed(4)}`} />
        <div className="my-1.5 border-t border-border" />
        <div className="text-xs font-bold text-foreground mb-0.5">All Time</div>
        <Row label="Requests" value={String(usage.total.total_requests)} />
        <Row label="Cost" value={`$${usage.total.total_cost.toFixed(4)}`} />
      </div>
    </div>
  );
}
