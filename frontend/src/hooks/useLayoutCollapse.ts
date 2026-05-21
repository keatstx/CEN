import { useCallback, useEffect, useState } from "react";

const LEFT_KEY = "cen:left-collapsed";
const RIGHT_KEY = "cen:right-collapsed";

function readBool(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeBool(key: string, value: boolean): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value ? "1" : "0");
  } catch {
    /* ignore quota / disabled storage */
  }
}

/**
 * Controls the collapse state of the left and right rails.
 *
 * State persists across reloads via localStorage. Default is expanded
 * for both rails (matches what most users want on first run).
 */
export function useLayoutCollapse(): {
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  toggleLeft: () => void;
  toggleRight: () => void;
} {
  const [leftCollapsed, setLeftCollapsed] = useState(() => readBool(LEFT_KEY));
  const [rightCollapsed, setRightCollapsed] = useState(() => readBool(RIGHT_KEY));

  useEffect(() => {
    writeBool(LEFT_KEY, leftCollapsed);
  }, [leftCollapsed]);

  useEffect(() => {
    writeBool(RIGHT_KEY, rightCollapsed);
  }, [rightCollapsed]);

  const toggleLeft = useCallback(() => setLeftCollapsed((v) => !v), []);
  const toggleRight = useCallback(() => setRightCollapsed((v) => !v), []);

  return { leftCollapsed, rightCollapsed, toggleLeft, toggleRight };
}
