"use client";

import { useMemo } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import { Header } from "@/components/header";
import { PositionsTable } from "@/components/positions-table";
import { OptionsTable } from "@/components/options-table";
import { OrdersTable } from "@/components/orders-table";
import { AccountPanel } from "@/components/account-panel";
import { StatsPanel } from "@/components/stats-panel";
import { ConfigPanel } from "@/components/config-panel";
import { ApiUsagePanel } from "@/components/api-usage-panel";
import { LogStream } from "@/components/log-stream";
import { TargetPanel } from "@/components/target-panel";
import { NewsPanel } from "@/components/news-panel";
import { CryptoTable } from "@/components/crypto-table";
import { GridLayout } from "@/components/grid-layout";
import { AccountMgmtPanel } from "@/components/account-mgmt-panel";

export default function Dashboard() {
  const { data, connected } = useWebSocket();

  const panels = useMemo(
    () => ({
      positions: <PositionsTable positions={data?.positions ?? null} />,
      options: <OptionsTable options={data?.options ?? null} />,
      crypto: <CryptoTable positions={data?.crypto ?? null} />,
      orders: <OrdersTable orders={data?.orders ?? null} />,
      account: <AccountPanel account={data?.account ?? null} />,
      target: <TargetPanel account={data?.account ?? null} />,
      stats: <StatsPanel stats={data?.stats ?? null} />,
      config: <ConfigPanel config={data?.config ?? null} />,
      "api-usage": <ApiUsagePanel usage={data?.api_usage ?? null} />,
      news: <NewsPanel news={data?.news ?? null} />,
      logs: <LogStream logs={data?.logs ?? null} />,
      "account-mgmt": <AccountMgmtPanel />,
    }),
    [data],
  );

  return (
    <div className="h-screen flex flex-col overflow-hidden p-1 gap-1">
      <Header status={data?.status ?? null} connected={connected} indices={data?.market_indices ?? []} />
      <div className="flex-1 min-h-0 overflow-y-auto">
        <GridLayout>{panels}</GridLayout>
      </div>
    </div>
  );
}
