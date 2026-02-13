"use client";

import { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from "chart.js";
import { getApiUrl } from "@/lib/utils";
import type { EquityCurveData } from "@/lib/types";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

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

  const dates = data.equity_curve.map(p => new Date(p.date).toLocaleDateString(undefined, { month: "short", day: "numeric" }));
  
  const chartData = {
    labels: dates,
    datasets: [
      {
        label: "Account",
        data: data.equity_curve.map(p => p.normalized),
        borderColor: "#ff9e2c",
        backgroundColor: "rgba(255, 158, 44, 0.1)",
        borderWidth: 2,
        pointRadius: 1,
        pointHoverRadius: 4,
        tension: 0.1,
      },
      ...(data.spy_curve?.length ? [{
        label: "SPY",
        data: data.spy_curve.map(p => p.normalized),
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 3,
        tension: 0.1,
      }] : []),
      ...(data.btc_curve?.length ? [{
        label: "BTC",
        data: data.btc_curve.map(p => p.normalized),
        borderColor: "#f59e0b",
        backgroundColor: "rgba(245, 158, 11, 0.1)",
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 3,
        tension: 0.1,
      }] : []),
    ],
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        border: { color: "#3a3a48" },
        grid: { color: "rgba(58, 58, 72, 0.3)" },
        ticks: { 
          color: "#94a3b8", 
          font: { size: 10 },
          maxTicksLimit: 8 
        },
      },
      y: {
        border: { color: "#3a3a48" },
        grid: { color: "rgba(58, 58, 72, 0.3)" },
        ticks: { 
          color: "#94a3b8", 
          font: { size: 10 },
          callback: (value) => `${Number(value).toFixed(0)}%`
        },
      },
    },
    plugins: {
      legend: {
        position: "top",
        labels: { 
          color: "#e2e8f0", 
          font: { size: 11 },
          usePointStyle: true,
          pointStyle: "line",
        },
      },
      tooltip: {
        backgroundColor: "rgba(15, 23, 42, 0.95)",
        titleColor: "#e2e8f0",
        bodyColor: "#e2e8f0",
        borderColor: "#3a3a48",
        borderWidth: 1,
        titleFont: { size: 11 },
        bodyFont: { size: 10 },
        callbacks: {
          title: (items) => {
            const idx = items[0]?.dataIndex;
            if (idx !== undefined && data.equity_curve[idx]) {
              const point = data.equity_curve[idx];
              return new Date(point.date).toLocaleDateString();
            }
            return "";
          },
          label: (item) => {
            const label = item.dataset.label || "";
            const value = Number(item.raw).toFixed(1);
            if (label === "Account") {
              const idx = item.dataIndex;
              const point = data.equity_curve[idx];
              const equity = point?.equity?.toLocaleString(undefined, { style: "currency", currency: "USD" }) || "N/A";
              return [`${label}: ${value}%`, `Equity: ${equity}`];
            }
            return `${label}: ${value}%`;
          },
        },
      },
    },
    interaction: {
      intersect: false,
      mode: "index",
    },
  };

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
      <div style={{ height: "280px" }}>
        <Line data={chartData} options={options} />
      </div>
    </div>
  );
}