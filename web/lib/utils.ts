import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Local dev: API on :2323, web on :3000/5000 — connect directly to :2323
 * Production: use API_BASE_URL env var
 */
function getApiBase(): string {
  // Use API_BASE_URL env var if set (production)
  if (process.env.API_BASE_URL) {
    return process.env.API_BASE_URL;
  }
  
  if (typeof window === "undefined") return "http://localhost:2323";
  // Empty port means nginx/prod is in front — use same origin
  if (window.location.port === "") return "";
  // Local dev — API is on :2323
  return `${window.location.protocol}//${window.location.hostname}:2323`;
}

export function getApiUrl(): string {
  return getApiBase();
}

export function getWsUrl(): string {
  // Use API_BASE_URL env var if set (production)
  if (process.env.API_BASE_URL) {
    const wsUrl = process.env.API_BASE_URL.replace(/^http/, "ws");
    return `${wsUrl}/ws`;
  }
  
  if (typeof window === "undefined") return "ws://127.0.0.1:2323/ws";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // Empty port means nginx/prod is in front — use same origin
  if (window.location.port === "") {
    return `${proto}//${window.location.host}/ws`;
  }
  // Local dev — API is on :2323 (use 127.0.0.1 to avoid IPv6 issues)
  return `${proto}//127.0.0.1:2323/ws`;
}
