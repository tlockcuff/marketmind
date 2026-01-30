import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Get API base URL
 * - Production (IP:port): API on same host, port 2323
 * - Docker/nginx (same origin): use relative path
 * - Local dev: API on :2323
 */
function getApiBase(): string {
  if (typeof window === "undefined") return "http://localhost:2323";
  
  // Empty port (80/443) means nginx is proxying — use same origin
  if (window.location.port === "") return "";
  
  // Production: API on same hostname, port 2323
  return `${window.location.protocol}//${window.location.hostname}:2323`;
}

export function getApiUrl(): string {
  return getApiBase();
}

export function getWsUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:2323/ws";
  
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  
  // Empty port (80/443) means nginx is proxying
  if (window.location.port === "") {
    return `${proto}//${window.location.host}/ws`;
  }
  
  // Production: WebSocket on same hostname, port 2323
  return `${proto}//${window.location.hostname}:2323/ws`;
}
