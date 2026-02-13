"use client";

import type { MarketStatus } from "@/lib/types";
import { useMarketHours } from "@/hooks/use-market-hours";

interface MarketBarProps {
  status: MarketStatus | null;
}

export function MarketBar({ status }: MarketBarProps) {
  const marketHoursText = useMarketHours({
    isOpen: status?.is_open ?? false,
    timeUntilOpen: status?.time_until_open ?? null,
    timeUntilClose: status?.time_until_close ?? null,
  });

  if (!status) {
    return (
      <div className="bg-card border border-border rounded-sm p-4">
        <div className="animate-pulse flex items-center gap-4">
          <div className="h-4 bg-muted rounded w-24" />
          <div className="h-4 bg-muted rounded w-32" />
          <div className="h-4 bg-muted rounded w-20" />
        </div>
      </div>
    );
  }

  const isOpen = status.is_open;
  const statusColor = isOpen ? "text-green-400" : "text-yellow-400";
  const statusDot = isOpen ? "bg-green-400" : "bg-yellow-400";

  return (
    <div className="bg-card border border-border rounded-sm p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${statusDot}`} />
            <span className={`text-sm font-medium ${statusColor}`}>
              {status.session}
            </span>
          </div>
          
          <div className="text-sm text-muted-foreground">
            {marketHoursText}
          </div>
          
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground uppercase tracking-wider">
              Bot:
            </span>
            <span className={`text-xs font-bold ${
              status.bot_running ? "text-green-400" : "text-red-400"
            }`}>
              {status.bot_running ? "RUNNING" : "STOPPED"}
            </span>
          </div>
        </div>

        <div className="text-xs text-muted-foreground">
          {status.current_time}
        </div>
      </div>
    </div>
  );
}