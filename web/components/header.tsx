"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { MarketStatus, MarketIndex } from "@/lib/types";
import { useMarketHours } from "@/hooks/use-market-hours";
import { DocsSlideover } from "@/components/docs-slideover";
import { getApiUrl } from "@/lib/utils";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

const INDEX_NAMES: Record<string, string> = {
  "SPY": "S&P 500 Index",
  "DIA": "Dow Jones Industrial Average",
  "IWM": "Russell 2000 Index",
  "QQQ": "Nasdaq 100 Index",
  "VIXY": "ProShares VIX Short-Term Futures ETF",
};

interface HeaderProps {
  status: MarketStatus | null;
  connected: boolean;
  indices: MarketIndex[];
}

export function Header({ status, connected, indices }: HeaderProps) {
  const [loading, setLoading] = useState(false);
  const pathname = usePathname();
  const mode = status?.trading_mode === "live" ? "LIVE" : "PAPER";
  const modeColor = mode === "LIVE" ? "text-red-400 font-bold" : "text-green-400";
  const botRunning = status?.bot_running ?? false;
  const botStatus = botRunning ? "RUNNING" : "STOPPED";
  const botColor = botRunning ? "text-green-400" : "text-red-400";
  const connDot = connected ? "bg-green-400" : "bg-red-400";

  const marketHoursText = useMarketHours({
    isOpen: status?.is_open ?? false,
    timeUntilOpen: status?.time_until_open ?? null,
    timeUntilClose: status?.time_until_close ?? null,
  });

  async function toggleBot() {
    setLoading(true);
    try {
      const endpoint = botRunning ? "/api/bot/stop" : "/api/bot/start";
      await fetch(`${getApiUrl()}${endpoint}`, { method: "POST" });
    } catch {
      // status will update via websocket
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-between px-4 py-2 bg-[#12121a] border border-border rounded-sm">
      <div className="flex items-center gap-4">
        <span className="text-[#ff9e2c] font-bold text-sm tracking-wider">MARKETMIND</span>
        <Link
          href="/"
          className={`text-[11px] font-semibold uppercase tracking-wider transition-colors ${
            pathname === "/" ? "text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Dashboard
        </Link>
        <Link
          href="/analytics"
          className={`text-[11px] font-semibold uppercase tracking-wider transition-colors ${
            pathname === "/analytics" ? "text-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          Analytics
        </Link>
        <span className="text-[#3a3a48]">|</span>
        <span className={`text-xs font-semibold ${modeColor}`}>{mode}</span>
        <span className="text-[#3a3a48]">|</span>
        <button
          onClick={toggleBot}
          disabled={loading}
          className={`relative inline-flex items-center h-6 w-20 rounded-full transition-all duration-200 ${
            botRunning
              ? "bg-green-500/20 hover:bg-green-500/30"
              : "bg-red-500/20 hover:bg-red-500/30"
          } ${loading ? "opacity-50 cursor-wait" : "cursor-pointer"}`}
          title={botRunning ? "Click to stop bot" : "Click to start bot"}
        >
          <span
            className={`absolute left-0.5 h-5 w-9 rounded-full transition-all duration-200 flex items-center justify-center text-[10px] font-bold ${
              botRunning
                ? "translate-x-9.5 bg-green-500 text-white shadow-lg"
                : "translate-x-0 bg-red-500 text-white shadow-lg"
            }`}
          >
            {loading ? "⋯" : botRunning ? "ON" : "OFF"}
          </span>
          <span className={`absolute text-[9px] font-medium ${
            botRunning ? "left-1.5 text-green-400" : "right-1.5 text-red-400"
          }`}>
            {botRunning ? "●" : "○"}
          </span>
        </button>
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

      <div className="flex items-center gap-3 text-xs">
        {indices.map((idx) => {
          const color = idx.change >= 0 ? "text-green-400" : "text-red-400";
          const arrow = idx.change >= 0 ? "▲" : "▼";
          const indexName = INDEX_NAMES[idx.symbol] || idx.symbol;
          return (
            <Tooltip key={idx.symbol}>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1.5 cursor-help">
                  <span className={idx.is_vix ? "text-purple-400 font-semibold" : "text-[#8a8a9a] font-medium"}>
                    {idx.symbol}
                  </span>
                  <span className="text-foreground font-medium">{idx.price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  <span className={`${color} font-medium`}>
                    {arrow} {Math.abs(idx.change_pct).toFixed(2)}%
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p>{indexName}</p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>

      <div className="flex items-center gap-4 text-xs">
        <span className="text-foreground font-semibold">{status?.current_time ?? "—"}</span>
        <DocsSlideover />
        <div className={`w-2.5 h-2.5 rounded-full ${connDot}`} title={connected ? "Connected" : "Disconnected"} />
      </div>
    </div>
  );
}
