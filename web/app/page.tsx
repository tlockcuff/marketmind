"use client";

import { useWebSocketData } from "@/components/websocket-provider";
import { AppShell } from "@/components/layout/app-shell";
import { EquityHero } from "@/components/overview/equity-hero";
import { PositionCards } from "@/components/overview/position-cards";
import { MarketBar } from "@/components/overview/market-bar";
import { ActivityFeed } from "@/components/overview/activity-feed";

export default function OverviewPage() {
  const { data } = useWebSocketData();

  return (
    <AppShell currentTab="overview">
      <div className="p-4 space-y-6">
        {/* Market Status Bar */}
        <MarketBar status={data?.status ?? null} />
        
        {/* Main Equity Hero */}
        <EquityHero account={data?.account ?? null} />
        
        {/* Position Summary Cards */}
        <PositionCards 
          positions={data?.positions ?? null} 
          crypto={data?.crypto ?? null} 
        />
        
        {/* Recent Activity */}
        <ActivityFeed logs={data?.logs ?? null} />
      </div>
    </AppShell>
  );
}
