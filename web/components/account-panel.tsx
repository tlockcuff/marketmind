"use client";

import type { Account } from "@/lib/types";
import { SkeletonRows } from "@/components/ui/skeleton";

interface Props {
  account: Account | null;
}

function Row({ label, value, className = "" }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex justify-between items-center py-0.5">
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className={`text-sm font-medium ${className}`}>{value}</span>
    </div>
  );
}

function formatMoney(n: number) {
  if (!n || n === 0) {
    return "$0.00";
  }
  // Show cents for small amounts (under $100)
  const decimals = Math.abs(n) < 100 ? 2 : 0;
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: decimals, maximumFractionDigits: 2 });
}

export function AccountPanel({ account }: Props) {
  if (!account) {
    return (
      <div className="border border-border rounded-sm bg-card">
        <div className="panel-header"><span className="panel-title">ACCOUNT</span></div>
        <div className="px-3 py-2"><SkeletonRows rows={6} /></div>
      </div>
    );
  }

  const plColor = account.daily_change >= 0 ? "pl-positive" : "pl-negative";
  const blocked = account.trading_blocked || account.account_blocked;

  return (
    <div className="border border-border rounded-sm bg-card">
      <div className="panel-header gap-2">
        <span className="panel-title">ACCOUNT</span>
        {blocked && <span className="text-xs text-red-400 font-bold">BLOCKED</span>}
      </div>
      <div className="px-3 py-2">
        <Row label="Equity" value={formatMoney(account.equity)} className="font-bold text-foreground text-base" />
        <Row label="Prev Close" value={formatMoney(account.last_equity)} />
        <Row
          label="Daily P/L"
          value={`${formatMoney(account.daily_change)} (${account.daily_change_pct >= 0 ? "+" : ""}${account.daily_change_pct?.toFixed(2)}%)`}
          className={`font-bold ${plColor}`}
        />
        <Row
          label="Total P/L"
          value={formatMoney(account.total_pnl)}
          className={`font-bold ${account.total_pnl >= 0 ? "pl-positive" : "pl-negative"}`}
        />
        <Row
          label="Realized P/L"
          value={formatMoney(account.realized_pnl)}
          className={account.realized_pnl >= 0 ? "pl-positive" : "pl-negative"}
        />
        <Row
          label="Unrealized P/L"
          value={formatMoney(account.unrealized_pnl)}
          className={account.unrealized_pnl >= 0 ? "pl-positive" : "pl-negative"}
        />
        <div className="my-1.5 border-t border-border" />
        <Row label="Cash" value={formatMoney(account.cash)} />
        <Row label="Buying Power" value={formatMoney(account.buying_power)} />
        <Row label="Long Value" value={formatMoney(account.long_market_value)} />
        {account.short_market_value !== 0 && (
          <Row label="Short Value" value={formatMoney(account.short_market_value)} className="text-red-400" />
        )}
        <div className="my-1.5 border-t border-border" />
        <Row label="Init Margin" value={formatMoney(account.initial_margin)} />
        <Row label="Maint Margin" value={formatMoney(account.maintenance_margin)} />
      </div>
    </div>
  );
}
