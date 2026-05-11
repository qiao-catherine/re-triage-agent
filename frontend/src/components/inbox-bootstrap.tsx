"use client";

/**
 * Auto-bootstrap the inbox connection on first load so the analyst doesn't
 * have to click through Settings. We point the agent-inbox internals at our
 * own server-side proxy (`/api/lg`) — the LangSmith API key lives only on
 * the server and is injected by the proxy, never persisted in the browser.
 *
 * Env vars (build-time, NEXT_PUBLIC_*, safe to ship to the bundle):
 *   NEXT_PUBLIC_GRAPH_ID         graph id (defaults to "deal_triage")
 *   NEXT_PUBLIC_INBOX_NAME       display name in the sidebar
 *
 * The actual LangSmith API key lives in server-only env vars
 * (LANGSMITH_API_KEY) read by /api/lg/[...path]/route.ts.
 */

import { useEffect } from "react";

import { AGENT_INBOXES_LOCAL_STORAGE_KEY } from "@/components/agent-inbox/constants";

const BOOTSTRAP_ID = "northbrook-default";

export function InboxBootstrap() {
  useEffect(() => {
    const graphId = process.env.NEXT_PUBLIC_GRAPH_ID || "deal_triage";
    const name = process.env.NEXT_PUBLIC_INBOX_NAME || "Deal Triage";

    // Build an absolute URL — the langgraph-sdk's `new URL(path, apiUrl)`
    // rejects a relative apiUrl. `window.location.origin` resolves to
    // whatever the analyst is viewing (localhost:3000, vercel.app, etc.)
    // so Next.js routes us back to the same origin's /api/lg proxy.
    const proxyUrl = `${window.location.origin}/api/lg`;

    try {
      const raw = window.localStorage.getItem(AGENT_INBOXES_LOCAL_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];

      // If a stale entry from an earlier build is still there (with a raw
      // deployment URL or relative /api/lg), overwrite it.
      const needsRewrite =
        !Array.isArray(parsed) ||
        parsed.length === 0 ||
        parsed[0]?.deploymentUrl !== proxyUrl;

      if (needsRewrite) {
        const inbox = {
          id: BOOTSTRAP_ID,
          graphId,
          deploymentUrl: proxyUrl,
          name,
          selected: true,
        };
        window.localStorage.setItem(
          AGENT_INBOXES_LOCAL_STORAGE_KEY,
          JSON.stringify([inbox]),
        );
      }
    } catch (e) {
      console.warn("InboxBootstrap: failed to seed inbox config", e);
    }
  }, []);

  return null;
}
