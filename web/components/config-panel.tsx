"use client";

import { useState, useCallback } from "react";
import type { Config } from "@/lib/types";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SkeletonRows } from "@/components/ui/skeleton";
import { getApiUrl } from "@/lib/utils";

interface Props {
  config: Config | null;
}

export function ConfigPanel({ config }: Props) {
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEdit = useCallback((key: string, value: string) => {
    setEdits((prev) => ({ ...prev, [key]: value }));
  }, []);

  const cancelEdit = useCallback((key: string) => {
    setEdits((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const saveEdits = useCallback(async () => {
    if (!config) return;
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, number | boolean> = {};
      for (const [key, raw] of Object.entries(edits)) {
        const meta = config.settings_meta[key];
        if (!meta) continue;
        if (meta.type === "bool") {
          payload[key] = raw === "true";
        } else if (meta.type === "int") {
          payload[key] = parseInt(raw, 10);
        } else {
          payload[key] = parseFloat(raw);
        }
      }
      const res = await fetch(`${getApiUrl()}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail));
        return;
      }
      setEdits({});
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }, [config, edits]);

  const resetAll = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await fetch(`${getApiUrl()}/api/config`, { method: "DELETE" });
      setEdits({});
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }, []);

  if (!config) {
    return (
      <div className="flex-1 min-h-0 border border-border rounded-sm bg-card flex flex-col">
        <div className="panel-header"><span className="panel-title">CONFIG</span></div>
        <div className="px-3 py-2"><SkeletonRows rows={8} /></div>
      </div>
    );
  }

  const { values, overrides, settings_meta } = config;

  // Group by section
  const sections: Record<string, string[]> = {};
  for (const [key, meta] of Object.entries(settings_meta)) {
    const sec = meta.section;
    if (!sections[sec]) sections[sec] = [];
    sections[sec].push(key);
  }

  const hasEdits = Object.keys(edits).length > 0;
  const hasOverrides = overrides.length > 0;

  const formatLabel = (key: string, meta: { label: string }) => meta.label;

  return (
    <div className="flex-1 min-h-0 border border-border rounded-sm bg-card flex flex-col">
      <div className="panel-header flex items-center justify-between">
        <span className="panel-title">CONFIG</span>
        <div className="flex gap-1">
          {hasOverrides && (
            <button
              onClick={resetAll}
              disabled={saving}
              className="text-[10px] px-1.5 py-0.5 rounded bg-muted hover:bg-destructive hover:text-destructive-foreground transition-colors"
            >
              Reset
            </button>
          )}
          {hasEdits && (
            <button
              onClick={saveEdits}
              disabled={saving}
              className="text-[10px] px-1.5 py-0.5 rounded bg-primary text-primary-foreground hover:bg-primary/80 transition-colors"
            >
              {saving ? "..." : "Save"}
            </button>
          )}
        </div>
      </div>
      {error && (
        <div className="px-3 py-1 text-[10px] text-destructive bg-destructive/10">{error}</div>
      )}
      <ScrollArea className="flex-1 min-h-0">
        <div className="px-2 py-1.5">
          {Object.entries(sections).map(([section, keys]) => (
            <div key={section} className="mb-2 last:mb-0">
              <div className="text-xs font-bold text-foreground mb-1 pb-1 border-b border-border/50">
                {section}
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-4 -mx-0.5">
                {keys.map((key) => {
                  const meta = settings_meta[key];
                  const currentValue = values[key];
                  const isOverridden = overrides.includes(key);
                  const isEditing = key in edits;
                  const displayValue = isEditing ? edits[key] : String(currentValue);
                  const hasChanged = isEditing && displayValue !== String(currentValue);

                  return (
                    <div
                      key={key}
                      className={`flex flex-row items-center justify-between gap-0 py-0.5 px-0.5 rounded transition-colors ${
                        isEditing ? "bg-primary/5" : "hover:bg-muted/30"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1.5">
                        <label
                          className={`text-xs flex items-center gap-0.5 ${
                            isOverridden ? "text-primary font-medium" : "text-muted-foreground"
                          }`}
                        >
                          {formatLabel(key, meta)}
                          {isOverridden && (
                            <span className="text-[12px] text-[#ff9e2c] ml-2" title="Overridden">*</span>
                          )}
                          {hasChanged && (
                            <span className="text-[12px] text-[#ff9e2c] ml-2" title="Modified">●</span>
                          )}
                        </label>
                        {isEditing && (
                          <button
                            onClick={() => cancelEdit(key)}
                            className="text-[12px] text-destructive transition-colors shrink-0"
                            title="Cancel edit"
                          >
                            ×
                          </button>
                        )}
                      </div>
                      <div className="flex items-center justify-end">
                        {meta.type === "bool" ? (
                          <button
                            onClick={() => {
                              const next = isEditing
                                ? edits[key] === "true" ? "false" : "true"
                                : currentValue ? "false" : "true";
                              handleEdit(key, next);
                            }}
                            className={`text-[10px] px-1.5 py-0.5 rounded transition-all ${
                              (isEditing ? edits[key] === "true" : currentValue)
                                ? "bg-green-500/20 text-green-400 hover:bg-green-500/30"
                                : "bg-muted text-muted-foreground hover:bg-muted/80"
                            } ${hasChanged ? "ring-1 ring-primary/50" : ""}`}
                          >
                            {(isEditing ? edits[key] === "true" : currentValue) ? "ON" : "OFF"}
                          </button>
                        ) : (
                          <input
                            type="number"
                            value={displayValue}
                            onChange={(e) => handleEdit(key, e.target.value)}
                            onBlur={() => {
                              // Auto-save on blur if value changed
                              if (hasChanged) {
                                // Could auto-save here, but keeping manual save for now
                              }
                            }}
                            step={meta.type === "float" ? "0.01" : "1"}
                            min={meta.min}
                            max={meta.max}
                            className={`w-full min-w-[60px] text-right text-xs font-medium bg-background/60 border rounded px-1 py-0.5 transition-all [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none ${
                              hasChanged
                                ? "border-primary/50 ring-1 ring-primary/30"
                                : "border-border hover:border-muted-foreground/50"
                            } focus:border-primary focus:ring-1 focus:ring-primary/50 focus:outline-none`}
                          />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
