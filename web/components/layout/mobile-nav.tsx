"use client";

import { useRouter, usePathname } from "next/navigation";
import { Home, TrendingUp, BarChart3, Activity } from "lucide-react";

interface MobileNavProps {
  currentTab?: string;
  onTabChange?: (tab: string) => void;
}

const tabs = [
  {
    id: "overview",
    label: "Overview",
    icon: Home,
    href: "/"
  },
  {
    id: "positions",
    label: "Positions", 
    icon: TrendingUp,
    href: "/positions"
  },
  {
    id: "analytics",
    label: "Analytics",
    icon: BarChart3,
    href: "/analytics"
  },
  {
    id: "activity",
    label: "Activity",
    icon: Activity,
    href: "/activity"
  }
];

export function MobileNav({ currentTab, onTabChange }: MobileNavProps) {
  const router = useRouter();
  const pathname = usePathname();

  // Determine active tab from pathname if currentTab not provided
  let activeTab = currentTab;
  if (!activeTab) {
    if (pathname === "/") activeTab = "overview";
    else if (pathname.startsWith("/positions")) activeTab = "positions";
    else if (pathname.startsWith("/analytics")) activeTab = "analytics";
    else if (pathname.startsWith("/activity")) activeTab = "activity";
    else activeTab = "overview";
  }

  function handleTabClick(tab: typeof tabs[0]) {
    if (onTabChange) {
      onTabChange(tab.id);
    } else {
      router.push(tab.href);
    }
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-card/95 backdrop-blur-sm border-t border-border z-50 lg:hidden">
      <div className="flex items-center justify-around py-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab)}
              className={`flex flex-col items-center gap-1 px-3 py-2 min-h-[44px] transition-colors ${
                isActive
                  ? "text-[#ff9e2c]"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon size={20} />
              <span className="text-xs font-medium">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}