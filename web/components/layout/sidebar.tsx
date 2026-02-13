"use client";

import { useState } from "react";
import { getApiUrl } from "@/lib/utils";
import type { DashboardData } from "@/lib/types";

interface SidebarProps {
  data: DashboardData | null;
  connected: boolean;
}

function formatMoney(n: number) {
  if (!n || n === 0) return "$0.00";
  const decimals = Math.abs(n) < 100 ? 2 : 0;
  return n.toLocaleString("en-US", { 
    style: "currency", 
    currency: "USD", 
    minimumFractionDigits: decimals, 
    maximumFractionDigits: 2 
  });
}

export function Sidebar({ data, connected }: SidebarProps) {
  const [loading, setLoading] = useState(false);

  const account = data?.account;
  const positions = data?.positions ?? [];
  const cryptoPositions = data?.crypto ?? [];
  const totalPositions = positions.length + cryptoPositions.length;
  
  const winningPositions = [...positions, ...cryptoPositions].filter(p => p.unrealized_pl > 0).length;
  const losingPositions = totalPositions - winningPositions;

  const botRunning = data?.status?.bot_running ?? false;

  async function toggleBot() {
    if (loading) return;
    setLoading(true);
    try {
      const endpoint = botRunning ? "/api/bot/stop" : "/api/bot/start";
      await fetch(`${getApiUrl()}${endpoint}`, { method: "POST" });
    } catch {
      // Status will update via websocket
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="h-full bg-card border-r border-border p-4 space-y-6">
      {/* Account Equity */}
      <div className="space-y-3">
        <h2 className="text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
          Account
        </h2>
        
        <div className="space-y-2">
          <div className="text-2xl font-bold text-foreground">
            {account ? formatMoney(account.equity) : "$--"}
          </div>
          
          {account && (
            <div className="flex items-center gap-2">
              <span className={`text-sm font-medium ${
                account.daily_change >= 0 ? "text-green-400" : "text-red-400"
              }`}>
                {account.daily_change >= 0 ? "+" : ""}{formatMoney(account.daily_change)}
              </span>
              <span className={`text-xs ${
                account.daily_change_pct >= 0 ? "text-green-400" : "text-red-400"
              }`}>
                ({account.daily_change_pct >= 0 ? "+" : ""}{account.daily_change_pct?.toFixed(2)}%)
              </span>
            </div>
          )}

          <div className="text-xs text-muted-foreground">
            {data?.status?.trading_mode === "live" ? (
              <span className="text-red-400 font-bold">LIVE TRADING</span>
            ) : (
              <span className="text-green-400">PAPER TRADING</span>
            )}
          </div>
        </div>
      </div>

      {/* Bot Status Toggle */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
          Bot Status
        </h3>
        
        <button
          onClick={toggleBot}
          disabled={loading}
          className={`relative inline-flex items-center h-8 w-full rounded-sm transition-all duration-200 font-medium text-sm ${
            botRunning
              ? "bg-green-500/20 hover:bg-green-500/30 text-green-400"
              : "bg-red-500/20 hover:bg-red-500/30 text-red-400"
          } ${loading ? "opacity-50 cursor-wait" : "cursor-pointer"}`}
        >
          {loading ? "..." : botRunning ? "RUNNING" : "STOPPED"}
        </button>
      </div>

      {/* Position Summary */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
          Positions
        </h3>
        
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-background p-3 rounded-sm text-center">
            <div className="text-lg font-bold text-foreground">{totalPositions}</div>
            <div className="text-xs text-muted-foreground">Total</div>
          </div>
          <div className="bg-background p-3 rounded-sm text-center">
            <div className="text-lg font-bold text-green-400">{winningPositions}</div>
            <div className="text-xs text-muted-foreground">Winners</div>
          </div>
        </div>
        
        {losingPositions > 0 && (
          <div className="bg-background p-3 rounded-sm text-center">
            <div className="text-lg font-bold text-red-400">{losingPositions}</div>
            <div className="text-xs text-muted-foreground">Losers</div>
          </div>
        )}
      </div>

      {/* Market Indices Ticker */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
          Market
        </h3>
        
        <div className="space-y-2">
          {(data?.market_indices ?? []).map((idx) => (
            <div key={idx.symbol} className="flex items-center justify-between text-xs">
              <span className={idx.is_vix ? "text-purple-400" : "text-muted-foreground"}>
                {idx.symbol}
              </span>
              <div className="flex items-center gap-1">
                <span className="text-foreground">
                  {idx.price.toFixed(2)}
                </span>
                <span className={idx.change >= 0 ? "text-green-400" : "text-red-400"}>
                  {idx.change >= 0 ? "▲" : "▼"} {Math.abs(idx.change_pct).toFixed(2)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Connection Status */}
      <div className="pt-4 border-t border-border">
        <div className="flex items-center gap-2 text-xs">
          <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400"}`} />
          <span className="text-muted-foreground">
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>
    </div>
  );
}