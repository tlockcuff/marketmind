"use client";

import { useState } from "react";
import { useWebSocketData } from "@/components/websocket-provider";
import { AppShell } from "@/components/layout/app-shell";

type FilterType = "all" | "trades" | "orders" | "system";

function formatLogEntry(log: string) {
  // Extract timestamp if present
  const timestampMatch = log.match(/^\[(\d{2}:\d{2}:\d{2})\]/);
  const timestamp = timestampMatch ? timestampMatch[1] : null;
  const message = timestampMatch ? log.substring(timestampMatch[0].length).trim() : log;

  // Determine log type and color
  let type: FilterType = "system";
  let color = "text-muted-foreground";
  let bgColor = "bg-transparent";
  
  if (message.includes("BUY") || message.includes("SELL")) {
    type = "trades";
    color = "text-blue-400";
    bgColor = "bg-blue-400/5";
  } else if (message.includes("ORDER") || message.includes("FILLED")) {
    type = "orders";
    color = "text-green-400";
    bgColor = "bg-green-400/5";
  } else if (message.includes("ERROR") || message.includes("FAILED")) {
    type = "system";
    color = "text-red-400";
    bgColor = "bg-red-400/5";
  } else if (message.includes("SIGNAL") || message.includes("SCORE")) {
    type = "system";
    color = "text-[#ff9e2c]";
    bgColor = "bg-[#ff9e2c]/5";
  }

  return { timestamp, message, type, color, bgColor };
}

export default function ActivityPage() {
  const { data } = useWebSocketData();
  const [filter, setFilter] = useState<FilterType>("all");

  const logs = data?.logs ?? [];
  
  // Process and filter logs
  const processedLogs = logs
    .map(formatLogEntry)
    .reverse() // Most recent first
    .filter(log => filter === "all" || log.type === filter);

  const filters = [
    { id: "all", label: "All", count: logs.length },
    { id: "trades", label: "Trades", count: logs.filter(l => formatLogEntry(l).type === "trades").length },
    { id: "orders", label: "Orders", count: logs.filter(l => formatLogEntry(l).type === "orders").length },
    { id: "system", label: "System", count: logs.filter(l => formatLogEntry(l).type === "system").length },
  ];

  return (
    <AppShell currentTab="activity">
      <div className="p-4">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-foreground mb-2">Activity Feed</h1>
          <p className="text-sm text-muted-foreground">
            Real-time stream of bot activity, trades, and system events
          </p>
        </div>

        {/* Filters */}
        <div className="mb-6 flex items-center gap-1">
          {filters.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id as FilterType)}
              className={`px-4 py-2 text-sm font-medium rounded-sm transition-colors ${
                filter === f.id
                  ? "bg-[#ff9e2c] text-black"
                  : "bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              {f.label} ({f.count})
            </button>
          ))}
        </div>

        {/* Activity Stream */}
        <div className="bg-card border border-border rounded-sm">
          {processedLogs.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <span className="text-4xl">📝</span>
              <p className="mt-4 text-lg">No activity found</p>
              <p className="text-sm">
                {filter === "all" ? "No logs available" : `No ${filter} events found`}
              </p>
            </div>
          ) : (
            <div className="max-h-[70vh] overflow-y-auto">
              {processedLogs.map((log, index) => (
                <div
                  key={index}
                  className={`border-b border-border/30 last:border-b-0 p-4 hover:bg-muted/10 transition-colors ${log.bgColor}`}
                >
                  <div className="flex gap-4">
                    {log.timestamp && (
                      <span className="text-xs text-muted-foreground font-mono shrink-0 pt-0.5">
                        {log.timestamp}
                      </span>
                    )}
                    <span className={`${log.color} text-sm leading-relaxed flex-1`}>
                      {log.message}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Auto-scroll indicator */}
        {processedLogs.length > 0 && (
          <div className="mt-4 text-xs text-muted-foreground text-center">
            Showing {processedLogs.length} {filter === "all" ? "events" : filter} • Most recent first
          </div>
        )}
      </div>
    </AppShell>
  );
}