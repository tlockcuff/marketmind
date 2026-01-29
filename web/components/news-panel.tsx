"use client";

import { useState } from "react";
import type { NewsData } from "@/lib/types";
import { SkeletonRows } from "@/components/ui/skeleton";

interface Props {
  news: NewsData | null;
}

const ALL_SECTORS = ["All", "Technology", "Healthcare", "Finance", "Energy", "Consumer", "Crypto", "General"];

function timeAgo(iso: string): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function NewsPanel({ news }: Props) {
  const [sector, setSector] = useState("All");
  const loading = news === null;

  const articles = news?.articles ?? [];
  const filtered = sector === "All" ? articles : articles.filter((a) => a.sector === sector);

  return (
    <div className="h-full flex flex-col border border-border rounded-sm bg-card">
      <div className="panel-header justify-between">
        <span className="panel-title">NEWS</span>
        {!loading && (
          <div className="flex gap-1 overflow-x-auto">
            {ALL_SECTORS.map((s) => (
              <button
                key={s}
                onClick={() => setSector(s)}
                className={`px-2 py-0.5 rounded text-xs whitespace-nowrap transition-colors ${
                  sector === s
                    ? "bg-[#2a2a36] text-zinc-100 font-medium"
                    : "text-muted-foreground hover:text-zinc-300 hover:bg-[#1e1e28]"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
      {loading ? (
        <div className="px-3 py-3"><SkeletonRows rows={6} /></div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto px-3 py-1.5">
          {filtered.length === 0 ? (
            <p className="text-muted-foreground text-sm py-4 text-center">No news articles</p>
          ) : (
            <div className="space-y-1.5">
              {filtered.map((item, i) => (
                <div key={i} className="py-1.5 border-b border-border/50 last:border-0">
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-zinc-200 hover:text-blue-400 transition-colors leading-snug block"
                  >
                    {item.headline}
                  </a>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[11px] text-muted-foreground">{item.source}</span>
                    <span className="text-[11px] text-muted-foreground/60">{timeAgo(item.created_at)}</span>
                    {item.symbols.slice(0, 4).map((sym) => (
                      <span
                        key={sym}
                        className="text-[10px] bg-[#1e1e28] text-cyan-400 px-1.5 py-0.5 rounded font-medium"
                      >
                        {sym}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
