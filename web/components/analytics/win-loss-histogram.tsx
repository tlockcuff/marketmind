"use client";

import { useMemo } from "react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell } from "recharts";
import type { ClosedTrade } from "@/lib/types";

interface Props {
  trades: ClosedTrade[];
}

export function WinLossHistogram({ trades }: Props) {
  const buckets = useMemo(() => {
    if (!trades.length) return [];
    const pnls = trades.map((t) => t.pnl);
    const min = Math.min(...pnls);
    const max = Math.max(...pnls);
    const range = max - min;
    if (range === 0) return [{ label: `$${min.toFixed(0)}`, count: trades.length, value: min }];
    const numBuckets = Math.min(20, Math.max(5, Math.ceil(Math.sqrt(trades.length))));
    const step = range / numBuckets;
    const result: { label: string; count: number; value: number }[] = [];
    for (let i = 0; i < numBuckets; i++) {
      const lo = min + i * step;
      const hi = lo + step;
      const count = pnls.filter((p) => (i === numBuckets - 1 ? p >= lo && p <= hi : p >= lo && p < hi)).length;
      const mid = (lo + hi) / 2;
      result.push({ label: `$${mid.toFixed(0)}`, count, value: mid });
    }
    return result;
  }, [trades]);

  if (!trades.length) {
    return (
      <ChartShell title="WIN/LOSS DISTRIBUTION">
        <Empty />
      </ChartShell>
    );
  }

  return (
    <ChartShell title="WIN/LOSS DISTRIBUTION">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={buckets} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid stroke="#252530" strokeDasharray="3 3" />
          <XAxis
            dataKey="label"
            tick={{ fill: "#8a8a9a", fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: "#252530" }}
            interval={Math.max(0, Math.floor(buckets.length / 8))}
          />
          <YAxis
            tick={{ fill: "#8a8a9a", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#252530" }}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{ background: "#12121a", border: "1px solid #252530", borderRadius: 4, fontSize: 12 }}
            labelStyle={{ color: "#8a8a9a" }}
            formatter={(v: number | undefined) => [v ?? 0, "Trades"]}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {buckets.map((b, i) => (
              <Cell key={i} fill={b.value >= 0 ? "#10b981" : "#ef4444"} fillOpacity={0.8} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

function ChartShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border border-border rounded-sm bg-card">
      <div className="px-3 py-2 border-b border-border">
        <span className="text-[12px] font-bold text-[#ff9e2c] uppercase tracking-wider">{title}</span>
      </div>
      <div className="p-3">{children}</div>
    </div>
  );
}

function Empty() {
  return <div className="flex items-center justify-center h-[280px] text-muted-foreground text-sm">No data</div>;
}
