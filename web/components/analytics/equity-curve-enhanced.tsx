"use client";

import { useEffect, useState } from "react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from "recharts";
import { getApiUrl } from "@/lib/utils";
import type { EquityCurveData } from "@/lib/types";

interface Props {
  range: string;
}

export function EquityCurveEnhanced({ range }: Props) {
  const [data, setData] = useState<EquityCurveData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${getApiUrl()}/api/analytics/equity-curve?range=${range}`);
        const json = await res.json();
        if (json.error) {
          setError(json.error);
        } else {
          setData(json);
        }
      } catch (e: any) {
        setError(e.message ?? "Failed to fetch equity curve");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [range]);

  if (loading) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Equity Curve vs Benchmarks</h3>
        <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
          Loading equity curve...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Equity Curve vs Benchmarks</h3>
        <div className="text-red-400 text-sm">{error}</div>
      </div>
    );
  }

  if (!data?.equity_curve?.length) {
    return (
      <div className="border border-border rounded-sm bg-card p-4">
        <h3 className="text-sm font-medium mb-3">Equity Curve vs Benchmarks</h3>
        <div className="text-muted-foreground text-sm">No equity data available</div>
      </div>
    );
  }

  // Merge data for recharts
  const chartData = data.equity_curve.map((point, index) => {
    const result: any = {
      date: new Date(point.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      account: point.normalized,
      equity: point.equity,
    };
    
    if (data.spy_curve && data.spy_curve[index]) {
      result.SPY = data.spy_curve[index].normalized;
    }
    
    if (data.btc_curve && data.btc_curve[index]) {
      result.BTC = data.btc_curve[index].normalized;
    }
    
    return result;
  });

  // Calculate performance metrics
  const firstEquity = data.equity_curve[0]?.normalized || 100;
  const lastEquity = data.equity_curve[data.equity_curve.length - 1]?.normalized || 100;
  const accountReturn = ((lastEquity - firstEquity) / firstEquity * 100);
  
  const firstSpy = data.spy_curve?.[0]?.normalized || 100;
  const lastSpy = data.spy_curve?.[data.spy_curve.length - 1]?.normalized || 100;
  const spyReturn = data.spy_curve?.length ? ((lastSpy - firstSpy) / firstSpy * 100) : null;

  const firstBtc = data.btc_curve?.[0]?.normalized || 100;
  const lastBtc = data.btc_curve?.[data.btc_curve.length - 1]?.normalized || 100;
  const btcReturn = data.btc_curve?.length ? ((lastBtc - firstBtc) / firstBtc * 100) : null;

  return (
    <div className="border border-border rounded-sm bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium">Equity Curve vs Benchmarks</h3>
        <div className="flex gap-4 text-xs">
          <span className="text-[#ff9e2c]">
            Account: {accountReturn >= 0 ? "+" : ""}{accountReturn.toFixed(1)}%
          </span>
          {spyReturn !== null && (
            <span className="text-[#3b82f6]">
              SPY: {spyReturn >= 0 ? "+" : ""}{spyReturn.toFixed(1)}%
            </span>
          )}
          {btcReturn !== null && (
            <span className="text-[#f59e0b]">
              BTC: {btcReturn >= 0 ? "+" : ""}{btcReturn.toFixed(1)}%
            </span>
          )}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
          <CartesianGrid stroke="#252530" strokeDasharray="3 3" />
          <XAxis 
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            tickFormatter={(value) => `${value.toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "rgba(15, 23, 42, 0.95)",
              border: "1px solid #3a3a48",
              borderRadius: "4px",
              color: "#e2e8f0",
              fontSize: "11px"
            }}
            formatter={(value: any, name?: string, props?: any) => {
              const displayName = name || "";
              if (displayName === "account") {
                const equity = props?.payload?.equity;
                const equityStr = equity?.toLocaleString(undefined, { style: "currency", currency: "USD" }) || "N/A";
                return [`${Number(value).toFixed(1)}% (${equityStr})`, "Account"];
              }
              return [`${Number(value).toFixed(1)}%`, displayName];
            }}
            labelFormatter={(date) => date}
          />
          <Legend 
            wrapperStyle={{ color: "#e2e8f0", fontSize: "11px" }}
          />
          <Line
            type="monotone"
            dataKey="account"
            stroke="#ff9e2c"
            strokeWidth={2}
            dot={false}
            name="Account"
          />
          {data.spy_curve?.length && (
            <Line
              type="monotone"
              dataKey="SPY"
              stroke="#3b82f6"
              strokeWidth={1.5}
              dot={false}
              name="SPY"
            />
          )}
          {data.btc_curve?.length && (
            <Line
              type="monotone"
              dataKey="BTC"
              stroke="#f59e0b"
              strokeWidth={1.5}
              dot={false}
              name="BTC"
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}