"use client";

import { useState } from "react";
import type { Position, CryptoPosition } from "@/lib/types";
import { PositionCard } from "./position-card";

interface PositionsListProps {
  positions: Position[] | null;
  crypto: CryptoPosition[] | null;
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

function PositionsTable({ 
  positions, 
  isCrypto = false 
}: { 
  positions: (Position | CryptoPosition)[]; 
  isCrypto?: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left py-3 px-3 text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
              Symbol
            </th>
            <th className="text-left py-3 px-3 text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
              Qty
            </th>
            <th className="text-right py-3 px-3 text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
              Avg Entry
            </th>
            <th className="text-right py-3 px-3 text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
              Current
            </th>
            <th className="text-right py-3 px-3 text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
              Market Value
            </th>
            <th className="text-right py-3 px-3 text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
              Unrealized P/L
            </th>
            <th className="text-right py-3 px-3 text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
              %
            </th>
            {!isCrypto && (
              <th className="text-center py-3 px-3 text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
                Score
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {positions.map((position, index) => {
            const isPositive = position.unrealized_pl >= 0;
            const rowBg = index % 2 === 0 ? "bg-background/50" : "bg-transparent";
            const plColor = isPositive ? "text-green-400" : "text-red-400";
            const side = position.qty > 0 ? "LONG" : "SHORT";
            const qty = Math.abs(position.qty);

            return (
              <tr 
                key={`${position.symbol}-${isCrypto ? 'crypto' : 'stock'}`}
                className={`border-b border-border/30 hover:bg-muted/20 transition-colors ${rowBg}`}
              >
                <td className="py-3 px-3">
                  <div className="flex items-center gap-2">
                    <div>
                      <div className="font-bold text-foreground">{position.symbol}</div>
                      <div className="text-xs text-muted-foreground truncate max-w-32">
                        {position.name}
                      </div>
                    </div>
                    {isCrypto && (
                      <span className="text-xs font-medium px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded">
                        CRYPTO
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-3 px-3">
                  <div className="text-right">
                    <div className="font-medium text-foreground">{qty.toLocaleString()}</div>
                    <div className={`text-xs font-bold ${
                      side === "LONG" ? "text-blue-400" : "text-orange-400"
                    }`}>
                      {side}
                    </div>
                  </div>
                </td>
                <td className="py-3 px-3 text-right font-medium text-foreground">
                  ${formatPrice(position.avg_entry)}
                </td>
                <td className="py-3 px-3 text-right font-medium text-foreground">
                  ${formatPrice(position.current_price)}
                </td>
                <td className="py-3 px-3 text-right font-medium text-foreground">
                  {formatMoney(('market_value' in position ? position.market_value : null) || (position.qty * position.current_price))}
                </td>
                <td className={`py-3 px-3 text-right font-bold ${plColor}`}>
                  {formatMoney(position.unrealized_pl)}
                </td>
                <td className={`py-3 px-3 text-right font-medium ${plColor}`}>
                  {isPositive ? "+" : ""}{position.unrealized_plpc?.toFixed(2)}%
                </td>
                {!isCrypto && (
                  <td className="py-3 px-3 text-center">
                    {('score' in position && position.score !== null && position.score !== undefined) ? (
                      <span className="text-xs font-medium px-2 py-1 bg-[#ff9e2c]/20 text-[#ff9e2c] rounded">
                        {'score' in position && typeof position.score === 'number' ? position.score.toFixed(1) : '—'}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function PositionsList({ positions, crypto }: PositionsListProps) {
  const [activeTab, setActiveTab] = useState<"all" | "stocks" | "crypto">("all");
  
  const stockPositions = positions ?? [];
  const cryptoPositions = crypto ?? [];
  const allPositions = [
    ...stockPositions.map(p => ({ ...p, isCrypto: false })),
    ...cryptoPositions.map(c => ({ ...c, isCrypto: true }))
  ];

  let displayPositions = allPositions;
  if (activeTab === "stocks") displayPositions = stockPositions.map(p => ({ ...p, isCrypto: false }));
  if (activeTab === "crypto") displayPositions = cryptoPositions.map(c => ({ ...c, isCrypto: true }));

  if (allPositions.length === 0) {
    return (
      <div className="bg-card border border-border rounded-sm p-8 text-center">
        <div className="text-muted-foreground">
          <span className="text-4xl">📊</span>
          <p className="mt-4 text-lg">No open positions</p>
          <p className="text-sm text-muted-foreground">
            Positions will appear here when the bot opens trades
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          {[
            { id: "all", label: `All (${allPositions.length})` },
            { id: "stocks", label: `Stocks (${stockPositions.length})` },
            { id: "crypto", label: `Crypto (${cryptoPositions.length})` }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2 text-sm font-medium rounded-sm transition-colors ${
                activeTab === tab.id
                  ? "bg-[#ff9e2c] text-black"
                  : "bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Mobile: Cards */}
      <div className="lg:hidden space-y-4">
        {displayPositions.map((position) => (
          <PositionCard
            key={`${position.symbol}-${position.isCrypto ? 'crypto' : 'stock'}`}
            position={position}
            isCrypto={position.isCrypto}
          />
        ))}
      </div>

      {/* Desktop: Table */}
      <div className="hidden lg:block bg-card border border-border rounded-sm overflow-hidden">
        {activeTab === "all" ? (
          <div className="space-y-0">
            {stockPositions.length > 0 && (
              <div>
                <div className="px-4 py-2 bg-background border-b border-border">
                  <span className="text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
                    Stock Positions ({stockPositions.length})
                  </span>
                </div>
                <PositionsTable positions={stockPositions} isCrypto={false} />
              </div>
            )}
            {cryptoPositions.length > 0 && (
              <div>
                {stockPositions.length > 0 && <div className="border-t border-border" />}
                <div className="px-4 py-2 bg-background border-b border-border">
                  <span className="text-xs font-bold text-[#ff9e2c] uppercase tracking-wider">
                    Crypto Positions ({cryptoPositions.length})
                  </span>
                </div>
                <PositionsTable positions={cryptoPositions} isCrypto={true} />
              </div>
            )}
          </div>
        ) : (
          <PositionsTable 
            positions={displayPositions} 
            isCrypto={activeTab === "crypto"} 
          />
        )}
      </div>
    </div>
  );
}