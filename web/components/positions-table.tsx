"use client";

import type { Position } from "@/lib/types";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SkeletonTable } from "@/components/ui/skeleton";

interface Props {
  positions: Position[] | null;
}

function formatMoney(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
}

function formatQty(qty: number, symbol: string) {
  // Crypto pairs and very small quantities get more decimals
  const isCrypto = symbol.includes("USD") && !symbol.startsWith("T");
  if (qty >= 100) return qty.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (qty >= 1) return qty.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (isCrypto && qty < 0.01) return qty.toFixed(6);
  if (qty < 0.01) return qty.toFixed(6);
  return qty.toLocaleString("en-US", { maximumFractionDigits: 4 });
}

function plColor(n: number) {
  return n >= 0 ? "pl-positive" : "pl-negative";
}

export function PositionsTable({ positions }: Props) {
  const loading = positions === null;
  const totalPl = positions?.reduce((s, p) => s + p.unrealized_pl, 0) ?? 0;
  const totalValue = positions?.reduce((s, p) => s + p.market_value, 0) ?? 0;

  return (
    <div className="h-full flex flex-col border border-border rounded-sm bg-card">
      <div className="panel-header justify-between">
        <span className="panel-title">POSITIONS {!loading && `(${positions.length})`}</span>
        {!loading && positions.length > 0 && (
          <span className={`text-xs font-semibold ${plColor(totalPl)}`}>
            {formatMoney(totalPl)} | {formatMoney(totalValue)} value
          </span>
        )}
      </div>
      {loading ? (
        <div className="px-3 py-3"><SkeletonTable rows={5} cols={6} /></div>
      ) : (
        <ScrollArea className="flex-1 min-h-0">
          <Table>
            <TableHeader>
              <TableRow className="text-xs border-border hover:bg-transparent">
                <TableHead className="w-[180px]">Symbol</TableHead>
                <TableHead className="text-right w-[55px]">Qty</TableHead>
                <TableHead className="text-right w-[85px]">Entry</TableHead>
                <TableHead className="text-right w-[85px]">Now</TableHead>
                <TableHead className="text-right w-[95px]">P/L</TableHead>
                <TableHead className="text-right w-[65px]">%</TableHead>
                <TableHead>Reason</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {positions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground text-sm py-8">
                    No positions
                  </TableCell>
                </TableRow>
              ) : (
                positions.map((p) => (
                  <TableRow key={p.symbol} className="text-xs border-border">
                    <TableCell className="font-semibold">
                      <span className="text-cyan-400">{p.symbol}</span>
                      <span className="text-muted-foreground ml-2 text-[11px]">{p.name}</span>
                    </TableCell>
                    <TableCell className="text-right">{formatQty(p.qty, p.symbol)}</TableCell>
                    <TableCell className="text-right">{formatMoney(p.avg_entry)}</TableCell>
                    <TableCell className="text-right">{formatMoney(p.current_price)}</TableCell>
                    <TableCell className={`text-right font-semibold ${plColor(p.unrealized_pl)}`}>
                      {formatMoney(p.unrealized_pl)}
                    </TableCell>
                    <TableCell className={`text-right ${plColor(p.unrealized_plpc)}`}>
                      {(p.unrealized_plpc * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-muted-foreground text-[11px]">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="cursor-default">
                              {p.score != null && (
                                <Badge variant="outline" className="mr-1 text-[10px] px-1.5 py-0">
                                  {p.score}
                                </Badge>
                              )}
                              {p.rationale ?? "—"}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent side="left" className="max-w-xs text-xs">
                            {p.rationale ?? "No rationale available"}
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </ScrollArea>
      )}
    </div>
  );
}
