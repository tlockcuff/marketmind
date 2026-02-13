"use client";

import { useWebSocket } from "@/hooks/use-websocket";
import { Header } from "@/components/header";
import { Sidebar } from "@/components/layout/sidebar";
import { MobileNav } from "@/components/layout/mobile-nav";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: React.ReactNode;
  currentTab?: string;
  onTabChange?: (tab: string) => void;
}

export function AppShell({ children, currentTab, onTabChange }: AppShellProps) {
  const { data, connected } = useWebSocket();

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <div className="border-b border-border">
        <Header
          status={data?.status ?? null}
          connected={connected}
          indices={data?.market_indices ?? []}
        />
      </div>

      {/* Main layout */}
      <div className="flex h-[calc(100vh-57px)]">
        {/* Desktop sidebar */}
        <div className="hidden lg:block w-80 border-r border-border">
          <Sidebar data={data} connected={connected} />
        </div>

        {/* Main content */}
        <div className="flex-1 overflow-hidden">
          <div className={cn(
            "h-full overflow-auto",
            // Add padding bottom on mobile for bottom nav
            "pb-16 lg:pb-0"
          )}>
            {children}
          </div>
        </div>
      </div>

      {/* Mobile bottom navigation */}
      <div className="lg:hidden">
        <MobileNav currentTab={currentTab} onTabChange={onTabChange} />
      </div>
    </div>
  );
}