"use client";

import { useEffect } from "react";

/**
 * Run `fetch()` once on mount and every time the window regains focus.
 * Cheap "auto-refresh on tab return". No polling, no websockets.
 */
export function useFocusRefresh(fetch: () => void): void {
  useEffect(() => {
    fetch();
    const handler = () => fetch();
    window.addEventListener("focus", handler);
    return () => window.removeEventListener("focus", handler);
    // Mount only; `fetch` should be stable (useCallback in caller).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
