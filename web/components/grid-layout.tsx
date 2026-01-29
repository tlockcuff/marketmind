"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ResponsiveGridLayout,
  useContainerWidth,
  verticalCompactor,
} from "react-grid-layout";
import type { Layout, ResponsiveLayouts } from "react-grid-layout";
import "react-grid-layout/css/styles.css";
import DEFAULT_LAYOUTS_JSON from "@/config/grid-layouts.json";

const STORAGE_KEY = "grid-layout";
const DEFAULT_LAYOUTS = DEFAULT_LAYOUTS_JSON as unknown as ResponsiveLayouts;

function loadLayouts(): ResponsiveLayouts {
  if (typeof window === "undefined") return DEFAULT_LAYOUTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return DEFAULT_LAYOUTS;
}

function saveLayouts(layouts: ResponsiveLayouts) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layouts));
  } catch {}
}

interface GridLayoutProps {
  children: Record<string, React.ReactNode>;
}

export function GridLayout({ children }: GridLayoutProps) {
  const { width, containerRef } = useContainerWidth({ measureBeforeMount: true });

  // Load from localStorage on client only — useRef initializer runs during SSR
  // where window is undefined, so we must re-load in useEffect
  const [mounted, setMounted] = useState(false);
  const layoutsRef = useRef<ResponsiveLayouts>(DEFAULT_LAYOUTS);
  const shouldPersist = useRef(false);

  useEffect(() => {
    layoutsRef.current = loadLayouts();
    setMounted(true);
  }, []);

  const onLayoutChange = useCallback(
    (_layout: Layout, allLayouts: ResponsiveLayouts) => {
      layoutsRef.current = { ...layoutsRef.current, ...allLayouts };
      if (shouldPersist.current) {
        shouldPersist.current = false;
        saveLayouts(layoutsRef.current);
      }
    },
    [],
  );

  const flagPersist = useCallback(() => {
    shouldPersist.current = true;
    // Fallback: if onLayoutChange doesn't fire (deepEqual skips it),
    // save after the current call stack completes
    queueMicrotask(() => {
      if (shouldPersist.current) {
        shouldPersist.current = false;
        saveLayouts(layoutsRef.current);
      }
    });
  }, []);

  const items = useMemo(
    () =>
      Object.entries(children).map(([key, node]) => (
        <div key={key} className="grid-item">
          {node}
        </div>
      )),
    [children],
  );

  if (!mounted || width <= 0) {
    return <div ref={containerRef} />;
  }

  return (
    <div ref={containerRef}>
      <ResponsiveGridLayout
        className="layout"
        width={width}
        layouts={layoutsRef.current}
        breakpoints={{ lg: 1200, md: 900, sm: 0 }}
        cols={{ lg: 24, md: 20, sm: 12 }}
        rowHeight={25}
        dragConfig={{ handle: ".panel-header" }}
        onLayoutChange={onLayoutChange}
        onDragStop={flagPersist}
        onResizeStop={flagPersist}
        compactor={verticalCompactor}
        margin={[4, 4]}
      >
        {items}
      </ResponsiveGridLayout>
    </div>
  );
}
