"use client";

import { useEffect } from "react";

/**
 * Run `fetch()` once on mount and every time the window regains focus.
 *
 * Cheap "auto-refresh on tab return" — the analyst clicks Accept/Respond in
 * the For Review tab, switches to Done or Firm memory, and the data is fresh.
 * No polling, no websockets.
 */
export function useFocusRefresh(fetch: () => void): void {
  useEffect(() => {
    fetch();
    const handler = () => fetch();
    window.addEventListener("focus", handler);
    return () => window.removeEventListener("focus", handler);
    // We intentionally only run on mount; `fetch` should be stable (defined
    // with useCallback in the caller) or any change will be picked up by the
    // standard React effect closure semantics.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
