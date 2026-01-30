"use client";

import { useState, useCallback } from "react";
import { getApiUrl } from "@/lib/utils";

export function AccountMgmtPanel() {
  const [apiKey, setApiKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [wiping, setWiping] = useState(false);
  const [confirmWipe, setConfirmWipe] = useState(false);
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [currentKeys, setCurrentKeys] = useState<{
    api_key: string;
    secret_key: string;
    mode: string;
  } | null>(null);
  const [loaded, setLoaded] = useState(false);

  const loadKeys = useCallback(async () => {
    try {
      const res = await fetch(`${getApiUrl()}/api/keys`);
      if (res.ok) {
        setCurrentKeys(await res.json());
      }
    } catch {}
    setLoaded(true);
  }, []);

  if (!loaded) {
    loadKeys();
  }

  const saveKeys = useCallback(async () => {
    if (!apiKey || !secretKey) {
      setMsg({ text: "Both fields required", ok: false });
      return;
    }
    setSaving(true);
    setMsg(null);
    try {
      const res = await fetch(`${getApiUrl()}/api/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: apiKey,
          secret_key: secretKey,
          reset_data: true,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setMsg({ text: `Keys updated, data reset. Key: ${data.api_key}`, ok: true });
        setApiKey("");
        setSecretKey("");
        setCurrentKeys(null);
        setLoaded(false);
      } else {
        setMsg({ text: data.detail || "Failed", ok: false });
      }
    } catch (e) {
      setMsg({ text: String(e), ok: false });
    } finally {
      setSaving(false);
    }
  }, [apiKey, secretKey]);

  const wipeData = useCallback(async () => {
    setWiping(true);
    setMsg(null);
    try {
      const res = await fetch(`${getApiUrl()}/api/reset`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        setMsg({ text: "All paper trading data wiped", ok: true });
      } else {
        setMsg({ text: data.detail || "Failed", ok: false });
      }
    } catch (e) {
      setMsg({ text: String(e), ok: false });
    } finally {
      setWiping(false);
      setConfirmWipe(false);
    }
  }, []);

  return (
    <div className="flex-1 min-h-0 border border-border rounded-sm bg-card flex flex-col">
      <div className="panel-header">
        <span className="panel-title">ACCOUNT MANAGEMENT</span>
      </div>

      {msg && (
        <div
          className={`px-3 py-1 text-[10px] ${
            msg.ok
              ? "text-green-400 bg-green-500/10"
              : "text-destructive bg-destructive/10"
          }`}
        >
          {msg.text}
        </div>
      )}

      <div className="px-3 py-2 space-y-3 text-xs">
        {/* Current keys display */}
        {currentKeys && (
          <div className="space-y-1">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
              Current Keys ({currentKeys.mode})
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground w-14">API:</span>
              <span className="font-mono text-foreground">{currentKeys.api_key}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground w-14">Secret:</span>
              <span className="font-mono text-foreground">{currentKeys.secret_key}</span>
            </div>
          </div>
        )}

        {/* Update keys */}
        <div className="space-y-1.5 pt-1 border-t border-border/50">
          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
            Update Alpaca Keys
          </div>
          <input
            type="text"
            placeholder="API Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="w-full text-xs font-mono bg-background/60 border border-border rounded px-2 py-1 focus:border-primary focus:ring-1 focus:ring-primary/50 focus:outline-none"
          />
          <input
            type="password"
            placeholder="Secret Key"
            value={secretKey}
            onChange={(e) => setSecretKey(e.target.value)}
            className="w-full text-xs font-mono bg-background/60 border border-border rounded px-2 py-1 focus:border-primary focus:ring-1 focus:ring-primary/50 focus:outline-none"
          />
          <div className="text-[10px] text-muted-foreground">
            Saves to .env and resets all DB data (new account)
          </div>
          <button
            onClick={saveKeys}
            disabled={saving || !apiKey || !secretKey}
            className="text-[10px] px-2 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/80 transition-colors disabled:opacity-50"
          >
            {saving ? "Saving..." : "Update Keys & Reset Data"}
          </button>
        </div>

        {/* Wipe data */}
        <div className="space-y-1.5 pt-1 border-t border-border/50">
          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
            Reset Paper Account
          </div>
          <div className="text-[10px] text-muted-foreground">
            Wipe all trades, stats, logs, and config from the database. Keeps API keys.
          </div>
          {!confirmWipe ? (
            <button
              onClick={() => setConfirmWipe(true)}
              className="text-[10px] px-2 py-1 rounded bg-muted hover:bg-destructive hover:text-destructive-foreground transition-colors"
            >
              Wipe All Data
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={wipeData}
                disabled={wiping}
                className="text-[10px] px-2 py-1 rounded bg-destructive text-destructive-foreground hover:bg-destructive/80 transition-colors"
              >
                {wiping ? "Wiping..." : "Confirm Wipe"}
              </button>
              <button
                onClick={() => setConfirmWipe(false)}
                className="text-[10px] px-2 py-1 rounded bg-muted hover:bg-muted/80 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
