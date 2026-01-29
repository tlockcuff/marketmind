"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { ArrowDownToLine } from "lucide-react";
import { SkeletonRows } from "@/components/ui/skeleton";

interface Props {
  logs: string[] | null;
}

function getLogLevel(line: string): string {
  if (line.includes("ERROR") || line.includes("ERR")) return "text-red-400";
  if (line.includes("WARN")) return "text-yellow-400";
  if (line.includes("===")) return "text-cyan-400 font-bold";
  return "text-foreground";
}

function to12h(time24: string): string {
  const match = time24.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?/);
  if (!match) return time24;
  let h = parseInt(match[1], 10);
  const m = match[2];
  const s = match[3];
  const ampm = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return s ? `${h}:${m}:${s} ${ampm}` : `${h}:${m} ${ampm}`;
}

function parseLogLine(line: string): { time: string | null; message: string } {
  const parts = line.split("|", 3);
  if (parts.length >= 3) {
    return { time: to12h(parts[0].trim()), message: parts[2].trim() };
  }
  return { time: null, message: line };
}

export function LogStream({ logs }: Props) {
  const endRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const loading = logs === null;
  const [anchored, setAnchored] = useState(true);

  const scrollToBottom = useCallback(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  // Auto-scroll when anchored and new logs arrive
  useEffect(() => {
    if (anchored) scrollToBottom();
  }, [logs?.length, anchored, scrollToBottom]);

  // Track whether user has scrolled away from bottom
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    setAnchored(atBottom);
  }, []);

  return (
    <div className="h-full flex flex-col border border-border rounded-sm bg-card">
      <div className="panel-header">
        <span className="panel-title">ACTIVITY</span>
        <button
          onClick={() => { setAnchored(true); scrollToBottom(); }}
          className={`ml-auto p-0.5 rounded transition-colors ${anchored ? "text-muted-foreground/40" : "text-cyan-400 hover:text-cyan-300"}`}
          title="Scroll to bottom"
        >
          <ArrowDownToLine size={14} />
        </button>
      </div>
      {loading ? (
        <div className="px-3 py-3"><SkeletonRows rows={6} /></div>
      ) : (
        <div ref={containerRef} onScroll={handleScroll} className="flex-1 min-h-0 overflow-y-auto px-3 py-1.5">
          <div className="space-y-0.5">
            {logs.length === 0 ? (
              <p className="text-muted-foreground text-sm py-4 text-center">No log entries</p>
            ) : (
              logs.map((line, i) => {
                const { time, message } = parseLogLine(line);
                const color = getLogLevel(line);
                return (
                  <div key={i} className="flex gap-2 leading-5">
                    {time && <span className="text-muted-foreground text-xs shrink-0 w-[100px]">{time}</span>}
                    <span className={`text-xs ${color} break-all`}>{message}</span>
                  </div>
                );
              })
            )}
            <div ref={endRef} />
          </div>
        </div>
      )}
    </div>
  );
}
