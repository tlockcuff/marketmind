"use client";

import { useState, useEffect, useCallback } from "react";
import type { Account } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  account: Account | null;
}

export function TargetPanel({ account }: Props) {
  const [target, setTarget] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchTarget = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/target`);
      const data = await res.json();
      setTarget(data.target ?? null);
      if (data.target) setInput(String(data.target));
    } catch {}
  }, []);

  useEffect(() => {
    fetchTarget();
  }, [fetchTarget]);

  const submitTarget = async () => {
    setLoading(true);
    try {
      const value = input.trim() === "" ? null : parseFloat(input);
      await fetch(`${API_URL}/api/target`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: value }),
      });
      setTarget(value);
    } catch {}
    setLoading(false);
  };

  const clearTarget = async () => {
    setLoading(true);
    try {
      await fetch(`${API_URL}/api/target`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: null }),
      });
      setTarget(null);
      setInput("");
    } catch {}
    setLoading(false);
  };

  const dailyPL = account?.daily_change ?? 0;
  const progress = target && target > 0 ? Math.min(100, Math.max(0, (dailyPL / target) * 100)) : 0;
  const reached = target != null && dailyPL >= target;

  return (
    <div className="border border-border rounded-sm bg-card">
      <div className="panel-header gap-2">
        <span className="panel-title">DAILY TARGET</span>
        {reached && <span className="text-xs text-green-400 font-bold">REACHED</span>}
      </div>
      <div className="px-3 py-2 space-y-2">
        <div className="flex gap-2 items-center">
          <span className="text-muted-foreground text-xs">$</span>
          <input
            type="number"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitTarget()}
            placeholder="0"
            className="flex-1 bg-[#1e1e28] border border-border rounded px-2 py-1 text-sm text-foreground w-20 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          />
          <button
            onClick={submitTarget}
            disabled={loading}
            className="px-3 py-1 text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white rounded disabled:opacity-50"
          >
            Set
          </button>
          {target != null && (
            <button
              onClick={clearTarget}
              disabled={loading}
              className="px-3 py-1 text-xs font-semibold bg-zinc-600 hover:bg-zinc-500 text-white rounded disabled:opacity-50"
            >
              Clear
            </button>
          )}
        </div>

        {target != null && target > 0 && (
          <>
            <div className="w-full bg-[#1e1e28] rounded-full h-2.5">
              <div
                className={`h-2.5 rounded-full transition-all ${reached ? "bg-green-500" : "bg-blue-500"}`}
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex justify-between text-xs">
              <span className={`font-semibold ${dailyPL >= 0 ? "pl-positive" : "pl-negative"}`}>
                ${dailyPL.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
              </span>
              <span className="text-muted-foreground">
                / ${target.toLocaleString("en-US", { minimumFractionDigits: 0 })}
                {" "}({progress.toFixed(0)}%)
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
