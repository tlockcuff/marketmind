import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Local dev: API on :8000, web on :3000/5000 — connect directly to :8000
 * Production (nginx): same origin proxies everything
 */
function getApiBase(): string {
  if (typeof window === "undefined") return "http://localhost:8000";
  // Empty port means nginx/prod is in front — use same origin
  if (window.location.port === "") return "";
  // Local dev — API is on :8000
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export function getApiUrl(): string {
  return getApiBase();
}

export function getWsUrl(): string {
  if (typeof window === "undefined") return "ws://127.0.0.1:8000/ws";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // Empty port means nginx/prod is in front — use same origin
  if (window.location.port === "") {
    return `${proto}//${window.location.host}/ws`;
  }
  // Local dev — API is on :8000 (use 127.0.0.1 to avoid IPv6 issues)
  return `${proto}//127.0.0.1:8000/ws`;
}
