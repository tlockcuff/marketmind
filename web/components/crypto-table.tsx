"use client";

import type { CryptoPosition } from "@/lib/types";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SkeletonTable } from "@/components/ui/skeleton";

interface Props {
  positions: CryptoPosition[] | null;
}

function formatMoney(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
}

function plColor(n: number) {
  return n >= 0 ? "pl-positive" : "pl-negative";
}

export function CryptoTable({ positions }: Props) {
  const loading = positions === null;
  const totalPl = positions?.reduce((s, p) => s + p.unrealized_pl, 0) ?? 0;
  const totalValue = positions?.reduce((s, p) => s + p.current_price * p.qty, 0) ?? 0;

  return (
    <div className="h-full flex flex-col border border-border rounded-sm bg-card">
      <div className="panel-header justify-between">
        <span className="panel-title flex items-center gap-2">
          CRYPTO {!loading && `(${positions.length})`}
          <Badge variant="outline" className="text-[9px] px-1 py-0 text-orange-400 border-orange-400/50">
            24/7
          </Badge>
        </span>
        {!loading && positions.length > 0 && (
          <span className={`text-xs font-semibold ${plColor(totalPl)}`}>
            {formatMoney(totalPl)} | {formatMoney(totalValue)} value
          </span>
        )}
      </div>
      {loading ? (
        <div className="px-3 py-3"><SkeletonTable rows={3} cols={8} /></div>
      ) : (
        <ScrollArea className="flex-1 min-h-0">
          <Table>
            <TableHeader>
              <TableRow className="text-xs border-border hover:bg-transparent">
                <TableHead className="w-[140px]">Symbol</TableHead>
                <TableHead className="text-right w-[65px]">Dir</TableHead>
                <TableHead className="text-right w-[65px]">Qty</TableHead>
                <TableHead className="text-right w-[85px]">Entry</TableHead>
                <TableHead className="text-right w-[85px]">Now</TableHead>
                <TableHead className="text-right w-[95px]">P/L</TableHead>
                <TableHead className="text-right w-[65px]">%</TableHead>
                <TableHead className="text-right w-[55px]">Score</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {positions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground text-sm py-8">
                    No crypto positions
                  </TableCell>
                </TableRow>
              ) : (
                positions.map((p) => (
                  <TableRow key={p.symbol} className="text-xs border-border">
                    <TableCell className="font-semibold">
                      <span className="text-orange-400">{p.symbol}</span>
                    </TableCell>
                    <TableCell className="text-right capitalize">{p.direction}</TableCell>
                    <TableCell className="text-right">{p.qty}</TableCell>
                    <TableCell className="text-right">{formatMoney(p.avg_entry)}</TableCell>
                    <TableCell className="text-right">{formatMoney(p.current_price)}</TableCell>
                    <TableCell className={`text-right font-semibold ${plColor(p.unrealized_pl)}`}>
                      {formatMoney(p.unrealized_pl)}
                    </TableCell>
                    <TableCell className={`text-right ${plColor(p.unrealized_plpc)}`}>
                      {(p.unrealized_plpc * 100).toFixed(1)}%
                    </TableCell>
                    <TableCell className="text-right">
                      {p.score != null && (
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                          {p.score}
                        </Badge>
                      )}
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
