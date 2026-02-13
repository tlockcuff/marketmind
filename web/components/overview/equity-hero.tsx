"use client";

import type { Account } from "@/lib/types";

interface EquityHeroProps {
  account: Account | null;
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

export function EquityHero({ account }: EquityHeroProps) {
  if (!account) {
    return (
      <div className="bg-card border border-border rounded-sm p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-8 bg-muted rounded w-1/3" />
          <div className="h-12 bg-muted rounded w-1/2" />
          <div className="h-6 bg-muted rounded w-1/4" />
        </div>
      </div>
    );
  }

  const isPositive = account.daily_change >= 0;
  const changeColor = isPositive ? "text-green-400" : "text-red-400";
  const cardBorderColor = isPositive ? "border-green-400/20" : "border-red-400/20";
  
  return (
    <div className={`bg-card border rounded-sm p-6 ${cardBorderColor}`}>
      <div className="space-y-4">
        {/* Account Status */}
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
            Portfolio Equity
          </h2>
          <div className="flex items-center gap-2">
            <span className={`text-xs font-bold px-2 py-1 rounded-sm ${
              account.is_paper 
                ? "bg-green-500/20 text-green-400" 
                : "bg-red-500/20 text-red-400"
            }`}>
              {account.is_paper ? "PAPER" : "LIVE"}
            </span>
          </div>
        </div>

        {/* Main Equity Display */}
        <div className="space-y-2">
          <div className="text-3xl sm:text-4xl font-bold text-foreground">
            {formatMoney(account.equity)}
          </div>
          
          <div className="flex items-center gap-3">
            <span className={`text-lg font-semibold ${changeColor}`}>
              {isPositive ? "+" : ""}{formatMoney(account.daily_change)}
            </span>
            <span className={`text-sm font-medium ${changeColor}`}>
              ({isPositive ? "+" : ""}{account.daily_change_pct?.toFixed(2)}%)
            </span>
            <span className="text-sm text-muted-foreground">
              Today
            </span>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-border">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Cash
            </div>
            <div className="text-sm font-medium text-foreground">
              {formatMoney(account.cash)}
            </div>
          </div>
          
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Buying Power
            </div>
            <div className="text-sm font-medium text-foreground">
              {formatMoney(account.buying_power)}
            </div>
          </div>
          
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Unrealized P/L
            </div>
            <div className={`text-sm font-medium ${
              account.unrealized_pnl >= 0 ? "text-green-400" : "text-red-400"
            }`}>
              {formatMoney(account.unrealized_pnl)}
            </div>
          </div>
          
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Total P/L
            </div>
            <div className={`text-sm font-medium ${
              account.total_pnl >= 0 ? "text-green-400" : "text-red-400"
            }`}>
              {formatMoney(account.total_pnl)}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}