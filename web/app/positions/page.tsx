"use client";

import { useWebSocketData } from "@/components/websocket-provider";
import { AppShell } from "@/components/layout/app-shell";
import { PositionsList } from "@/components/positions/positions-list";

export default function PositionsPage() {
  const { data } = useWebSocketData();

  return (
    <AppShell currentTab="positions">
      <div className="p-4">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-foreground mb-2">Open Positions</h1>
          <p className="text-sm text-muted-foreground">
            Real-time view of all open stock and cryptocurrency positions
          </p>
        </div>
        
        <PositionsList 
          positions={data?.positions ?? null} 
          crypto={data?.crypto ?? null} 
        />
      </div>
    </AppShell>
  );
}