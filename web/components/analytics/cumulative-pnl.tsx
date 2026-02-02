"use client";

import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from "recharts";
import type { CumulativePnlPoint } from "@/lib/types";

interface Props {
  data: CumulativePnlPoint[];
}

export function CumulativePnlChart({ data }: Props) {
  if (!data.length) {
    return (
      <ChartShell title="CUMULATIVE P/L">
        <Empty />
      </ChartShell>
    );
  }

  const lastVal = data[data.length - 1]?.cumulative_pnl ?? 0;
  const color = lastVal >= 0 ? "#10b981" : "#ef4444";
  const gradId = lastVal >= 0 ? "cpGreen" : "cpRed";

  return (
    <ChartShell title="CUMULATIVE P/L">
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.3} />
              <stop offset="95%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#252530" strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#8a8a9a", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#252530" }}
            tickFormatter={(v: string) => {
              if (!v) return "";
              const d = new Date(v);
              return `${d.getMonth() + 1}/${d.getDate()}`;
            }}
          />
          <YAxis
            tick={{ fill: "#8a8a9a", fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: "#252530" }}
            tickFormatter={(v: number) => `$${v.toLocaleString()}`}
            width={72}
          />
          <ReferenceLine y={0} stroke="#8a8a9a" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{ background: "#12121a", border: "1px solid #252530", borderRadius: 4, fontSize: 12 }}
            labelStyle={{ color: "#8a8a9a" }}
            formatter={(v: number | undefined, _name: string | undefined, props: any) => {
              const entry = props.payload;
              return [`$${(v ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}`, `Cum P/L (${entry.symbol}: $${entry.pnl})`];
            }}
          />
          <Area type="monotone" dataKey="cumulative_pnl" stroke={color} fill={`url(#${gradId})`} strokeWidth={2} dot={false} />
        </AreaChart>
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
