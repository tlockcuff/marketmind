"use client";

import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from "recharts";
import type { SectorPnl } from "@/lib/types";

interface Props {
  data: SectorPnl[];
}

const COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16"];

export function SectorBreakdown({ data }: Props) {
  if (!data.length) {
    return (
      <ChartShell title="P/L BY SECTOR">
        <Empty />
      </ChartShell>
    );
  }

  // Use absolute values for pie sizing, keep original for display
  const chartData = data.map((d, i) => ({
    ...d,
    absVal: Math.abs(d.pnl),
    fill: COLORS[i % COLORS.length],
  }));

  return (
    <ChartShell title="P/L BY SECTOR">
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={chartData}
            dataKey="absVal"
            nameKey="sector"
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={100}
            strokeWidth={1}
            stroke="#0a0a0f"
          >
            {chartData.map((d, i) => (
              <Cell key={i} fill={d.fill} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#12121a", border: "1px solid #252530", borderRadius: 4, fontSize: 12 }}
            formatter={(_val: number | undefined, _name: string | undefined, props: any) => {
              const pnl = props.payload.pnl;
              const sign = pnl >= 0 ? "+" : "";
              return [`${sign}$${pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}`, props.payload.sector];
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "#8a8a9a" }}
            formatter={(value: string, entry: any) => {
              const pnl = entry.payload?.pnl ?? 0;
              const color = pnl >= 0 ? "#33d17a" : "#ff5555";
              const sign = pnl >= 0 ? "+" : "";
              return <span style={{ color: "#8a8a9a" }}>{value} <span style={{ color }}>{sign}${pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span></span>;
            }}
          />
        </PieChart>
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
