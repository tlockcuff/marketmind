"use client";

import { useWebSocketData } from "@/components/websocket-provider";
import { Header } from "@/components/header";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileNav } from "@/components/layout/mobile-nav";

interface AppShellProps {
  children: React.ReactNode;
  currentTab?: string;
  onTabChange?: (tab: string) => void;
}

export function AppShell({ children, currentTab, onTabChange }: AppShellProps) {
  const { data, connected } = useWebSocketData();

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Header — desktop only */}
      <div className="hidden lg:block border-b border-border shrink-0">
        <Header
          status={data?.status ?? null}
          connected={connected}
          indices={data?.market_indices ?? []}
        />
      </div>

      {/* Main layout */}
      <div className="flex flex-1 min-h-0">
        {/* Desktop sidebar */}
        <div className="hidden lg:block w-80 shrink-0 border-r border-border overflow-y-auto">
          <Sidebar data={data} connected={connected} />
        </div>

        {/* Main content */}
        <div className="flex-1 overflow-y-auto pb-20 lg:pb-0">
          {children}
        </div>
      </div>

      {/* Mobile bottom navigation */}
      <MobileNav currentTab={currentTab} onTabChange={onTabChange} />
    </div>
  );
}