"use client";

import { createContext, useContext } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import type { DashboardData } from "@/lib/types";

interface WebSocketContextType {
  data: DashboardData | null;
  connected: boolean;
}

const WebSocketContext = createContext<WebSocketContextType | null>(null);

export function useWebSocketData() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocketData must be used within WebSocketProvider");
  }
  return context;
}

interface WebSocketProviderProps {
  children: React.ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const { data, connected } = useWebSocket();

  return (
    <WebSocketContext.Provider value={{ data, connected }}>
      {children}
    </WebSocketContext.Provider>
  );
}