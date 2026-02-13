"use client";

import type { Position, CryptoPosition } from "@/lib/types";

interface PositionCardsProps {
  positions: Position[] | null;
  crypto: CryptoPosition[] | null;
}

function formatMoney(n: number) {
  if (!n || n === 0) return "$0.00";
  return n.toLocaleString("en-US", { 
    style: "currency", 
    currency: "USD", 
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function formatQty(qty: number) {
  if (qty >= 100) return qty.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (qty >= 1) return qty.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (qty < 0.01) return qty.toFixed(6);
  return qty.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

function PositionCard({ 
  symbol, 
  name,
  qty,
  unrealized_pl, 
  unrealized_plpc,
  isCrypto = false 
}: {
  symbol: string;
  name: string;
  qty: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  isCrypto?: boolean;
}) {
  const isPositive = unrealized_pl >= 0;
  const borderColor = isPositive ? "border-green-400/30" : "border-red-400/30";
  const bgColor = isPositive ? "bg-green-400/5" : "bg-red-400/5";
  const textColor = isPositive ? "text-green-400" : "text-red-400";

  return (
    <div className={`bg-card border rounded-sm p-3 ${borderColor} ${bgColor}`}>
      <div className="space-y-2">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="font-bold text-foreground text-sm sm:text-base">{symbol}</span>
            {isCrypto && (
              <span className="text-[10px] font-medium px-1 py-0.5 bg-purple-500/20 text-purple-400 rounded">
                C
              </span>
            )}
          </div>
          <span className="text-[10px] text-muted-foreground">
            {formatQty(Math.abs(qty))}
          </span>
        </div>

        {/* P/L Display */}
        <div>
          <div className={`text-lg font-bold ${textColor}`}>
            {formatMoney(unrealized_pl)}
          </div>
          <div className={`text-xs font-medium ${textColor}`}>
            {isPositive ? "+" : ""}{(unrealized_plpc * 100).toFixed(2)}%
          </div>
        </div>
      </div>
    </div>
  );
}

export function PositionCards({ positions, crypto }: PositionCardsProps) {
  const allPositions = [
    ...(positions ?? []).map(p => ({ ...p, isCrypto: false })),
    ...(crypto ?? []).map(c => ({ ...c, isCrypto: true }))
  ];

  if (allPositions.length === 0) {
    return (
      <div className="bg-card border border-border rounded-sm p-8 text-center">
        <div className="text-muted-foreground">
          <span className="text-2xl">📊</span>
          <p className="mt-2 text-sm">No open positions</p>
        </div>
      </div>
    );
  }

  // Sort by absolute P/L descending
  const sortedPositions = allPositions.sort((a, b) => 
    Math.abs(b.unrealized_pl) - Math.abs(a.unrealized_pl)
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-[#ff9e2c] uppercase tracking-wider">
          Open Positions ({allPositions.length})
        </h3>
      </div>
      
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {sortedPositions.map((position) => (
          <PositionCard
            key={`${position.symbol}-${position.isCrypto ? 'crypto' : 'stock'}`}
            symbol={position.symbol}
            name={position.name}
            qty={position.qty}
            unrealized_pl={position.unrealized_pl}
            unrealized_plpc={position.unrealized_plpc}
            isCrypto={position.isCrypto}
          />
        ))}
      </div>
    </div>
  );
}