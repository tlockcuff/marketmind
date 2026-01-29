"use client";

import type { Order } from "@/lib/types";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SkeletonTable } from "@/components/ui/skeleton";

interface Props {
  orders: Order[] | null;
}

export function OrdersTable({ orders }: Props) {
  const loading = orders === null;

  return (
    <div className="h-full flex flex-col border border-border rounded-sm bg-card">
      <div className="panel-header">
        <span className="panel-title">OPEN ORDERS {!loading && `(${orders.length})`}</span>
      </div>
      {loading ? (
        <div className="px-3 py-3"><SkeletonTable rows={3} cols={6} /></div>
      ) : (
        <ScrollArea className="flex-1 min-h-0 overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="text-xs border-border hover:bg-transparent">
                <TableHead className="w-[70px]">Symbol</TableHead>
                <TableHead className="w-[50px]">Side</TableHead>
                <TableHead className="text-right w-[55px]">Qty</TableHead>
                <TableHead className="w-[75px]">Type</TableHead>
                <TableHead className="text-right w-[85px]">Stop</TableHead>
                <TableHead className="text-right w-[85px]">Limit</TableHead>
                <TableHead className="w-[85px]">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground text-sm py-6">
                    No open orders
                  </TableCell>
                </TableRow>
              ) : (
                orders.map((o) => (
                  <TableRow key={o.id} className="text-xs border-border">
                    <TableCell className="text-cyan-400 font-semibold">{o.symbol}</TableCell>
                    <TableCell className={o.side.toLowerCase().includes("buy") ? "text-green-400 font-medium" : "text-red-400 font-medium"}>
                      {o.side.toUpperCase()}
                    </TableCell>
                    <TableCell className="text-right">{o.qty}</TableCell>
                    <TableCell>{o.type}</TableCell>
                    <TableCell className="text-right">
                      {o.stop_price ? `$${o.stop_price.toFixed(2)}` : "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      {o.limit_price ? `$${o.limit_price.toFixed(2)}` : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{o.status}</TableCell>
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
