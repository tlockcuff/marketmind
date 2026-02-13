"use client";

import type { Position, CryptoPosition } from "@/lib/types";

interface PositionCardProps {
  position: Position | CryptoPosition;
  isCrypto?: boolean;
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

function formatPrice(n: number) {
  return n.toLocaleString(undefined, { 
    minimumFractionDigits: 2, 
    maximumFractionDigits: 4 
  });
}

export function PositionCard({ position, isCrypto = false }: PositionCardProps) {
  const isPositive = position.unrealized_pl >= 0;
  const borderColor = isPositive ? "border-green-400/30" : "border-red-400/30";
  const bgColor = isPositive ? "bg-green-400/5" : "bg-red-400/5";
  const textColor = isPositive ? "text-green-400" : "text-red-400";

  const side = position.qty > 0 ? "LONG" : "SHORT";
  const qty = Math.abs(position.qty);

  return (
    <div className={`bg-card border rounded-sm p-4 ${borderColor} ${bgColor}`}>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-bold text-foreground text-xl">{position.symbol}</span>
            {isCrypto && (
              <span className="text-xs font-medium px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded">
                CRYPTO
              </span>
            )}
            {(('score' in position && position.score !== null && position.score !== undefined) || 
              ('score' in position && typeof position.score === 'number')) && (
              <span className="text-xs font-medium px-1.5 py-0.5 bg-[#ff9e2c]/20 text-[#ff9e2c] rounded">
                {'score' in position && typeof position.score === 'number' ? position.score.toFixed(1) : ''}
              </span>
            )}
          </div>
          <span className={`text-xs font-bold px-2 py-1 rounded ${
            side === "LONG" ? "bg-blue-500/20 text-blue-400" : "bg-orange-500/20 text-orange-400"
          }`}>
            {side}
          </span>
        </div>

        {/* Company name */}
        <div className="text-sm text-muted-foreground">
          {position.name}
        </div>

        {/* Position Details */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Quantity
            </div>
            <div className="text-sm font-medium text-foreground">
              {qty.toLocaleString()}
            </div>
          </div>

          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Avg Entry
            </div>
            <div className="text-sm font-medium text-foreground">
              ${formatPrice(position.avg_entry)}
            </div>
          </div>

          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Current Price
            </div>
            <div className="text-sm font-medium text-foreground">
              ${formatPrice(position.current_price)}
            </div>
          </div>

          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Market Value
            </div>
            <div className="text-sm font-medium text-foreground">
              {formatMoney(('market_value' in position ? position.market_value : null) || (position.qty * position.current_price))}
            </div>
          </div>
        </div>

        {/* P/L Display */}
        <div className="pt-3 border-t border-border space-y-2">
          <div className={`text-2xl font-bold ${textColor}`}>
            {formatMoney(position.unrealized_pl)}
          </div>
          <div className={`text-sm font-medium ${textColor}`}>
            {isPositive ? "+" : ""}{position.unrealized_plpc?.toFixed(2)}% Unrealized
          </div>
        </div>

        {/* Rationale (if available) */}
        {('rationale' in position && position.rationale) && (
          <div className="pt-3 border-t border-border">
            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
              Rationale
            </div>
            <div className="text-xs text-foreground bg-background p-2 rounded">
              {position.rationale}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}