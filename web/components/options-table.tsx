"use client";

import type { OptionsPosition } from "@/lib/types";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SkeletonTable } from "@/components/ui/skeleton";

interface Props {
  options: OptionsPosition[] | null;
}

function formatMoney(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0 });
}

export function OptionsTable({ options }: Props) {
  const loading = options === null;

  return (
    <div className="h-full flex flex-col border border-border rounded-sm bg-card">
      <div className="panel-header">
        <span className="panel-title">OPTIONS {!loading && `(${options.length})`}</span>
      </div>
      {loading ? (
        <div className="px-3 py-3"><SkeletonTable rows={3} cols={5} /></div>
      ) : (
        <ScrollArea className="flex-1 min-h-0">
          <Table>
            <TableHeader>
              <TableRow className="text-xs border-border hover:bg-transparent">
                <TableHead className="w-[95px]">Strategy</TableHead>
                <TableHead className="w-[65px]">Underlying</TableHead>
                <TableHead>Contract</TableHead>
                <TableHead className="text-right w-[105px]">Cost/Credit</TableHead>
                <TableHead className="text-right w-[95px]">Max Loss</TableHead>
                <TableHead className="text-right w-[95px]">Max Profit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {options.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground text-sm py-6">
                    No options positions
                  </TableCell>
                </TableRow>
              ) : (
                options.map((o, i) => (
                  <TableRow key={i} className="text-xs border-border">
                    <TableCell className="text-cyan-400 font-medium">{o.strategy}</TableCell>
                    <TableCell>{o.underlying}</TableCell>
                    <TableCell className="text-muted-foreground text-[11px] truncate max-w-[150px]">
                      {o.contracts?.[0] ?? "—"}
                    </TableCell>
                    <TableCell className={`text-right font-medium ${o.net_debit_credit > 0 ? "text-red-400" : "text-green-400"}`}>
                      {formatMoney(o.net_debit_credit)}
                    </TableCell>
                    <TableCell className="text-right text-red-400">{formatMoney(o.max_loss)}</TableCell>
                    <TableCell className="text-right text-green-400">{formatMoney(o.max_profit)}</TableCell>
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
