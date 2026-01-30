import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Local dev: API on :2323, web on :3000/5000 — connect directly to :2323
 * Production (nginx): same origin proxies everything
 */
function getApiBase(): string {
  if (typeof window === "undefined") return process.env.API_BASE_URL || "http://localhost:2323";
  // Empty port means nginx/prod is in front — use same origin
  if (window.location.port === "") return "";
  // Local dev — API is on :2323
  return process.env.API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:2323`;
}

export function getApiUrl(): string {
  return getApiBase();
}

export function getWsUrl(): string {
  if (typeof window === "undefined") return process.env.API_BASE_URL ? `${process.env.API_BASE_URL}/ws` : "ws://127.0.0.1:2323/ws";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // Empty port means nginx/prod is in front — use same origin
  if (window.location.port === "") {
    return `${proto}//${window.location.host}/ws`;
  }
  // Local dev — API is on :2323 (use 127.0.0.1 to avoid IPv6 issues)
  return process.env.API_BASE_URL ? `${process.env.API_BASE_URL}/ws` : `${proto}//127.0.0.1:2323/ws`;
}
