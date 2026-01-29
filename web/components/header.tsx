"use client";

import type { MarketStatus } from "@/lib/types";
import { useMarketHours } from "@/hooks/use-market-hours";
import { DocsSlideover } from "@/components/docs-slideover";

interface HeaderProps {
  status: MarketStatus | null;
  connected: boolean;
}

export function Header({ status, connected }: HeaderProps) {
  const mode = status?.trading_mode === "live" ? "LIVE" : "PAPER";
  const modeColor = mode === "LIVE" ? "text-red-400 font-bold" : "text-green-400";
  const botStatus = status?.bot_running ? "RUNNING" : "STOPPED";
  const botColor = status?.bot_running ? "text-green-400" : "text-red-400";
  const connDot = connected ? "bg-green-400" : "bg-red-400";

  const marketHoursText = useMarketHours({
    isOpen: status?.is_open ?? false,
    timeUntilOpen: status?.time_until_open ?? null,
    timeUntilClose: status?.time_until_close ?? null,
  });

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-[#12121a] border border-border rounded-sm">
      <div className="flex items-center gap-4">
        <span className="text-[#ff9e2c] font-bold text-sm tracking-wider">MARKETMIND</span>
        <span className={`text-xs font-semibold ${modeColor}`}>{mode}</span>
        <span className="text-[#3a3a48]">|</span>
        <span className={`text-xs font-semibold ${botColor}`}>{botStatus}</span>
      </div>

      <div className="flex items-center gap-4 text-xs">
        <span className={status?.is_open ? "text-green-400 font-medium" : "text-yellow-400 font-medium"}>
          {status?.session ?? "—"}
        </span>
        <span className="text-[#3a3a48]">|</span>
        <span className={status?.is_open ? "text-green-400 font-medium" : "text-yellow-400 font-medium"}>
          {marketHoursText}
        </span>
      </div>

      <div className="flex items-center gap-4 text-xs">
        <span className="text-foreground font-semibold">{status?.current_time ?? "—"}</span>
        <DocsSlideover />
        <div className={`w-2.5 h-2.5 rounded-full ${connDot}`} title={connected ? "Connected" : "Disconnected"} />
      </div>
    </div>
  );
}
