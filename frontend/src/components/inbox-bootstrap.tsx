"use client";

/**
 * Auto-bootstrap the inbox connection on first load so the analyst doesn't
 * have to click through Settings. Points the agent-inbox internals at our
 * `/api/lg` proxy; the LangSmith API key stays server-side.
 *
 * Build-time env (NEXT_PUBLIC_*, safe to ship to the bundle):
 *   NEXT_PUBLIC_GRAPH_ID         graph id (default "deal_triage")
 *   NEXT_PUBLIC_INBOX_NAME       sidebar display name
 *
 * Server-only env (read by /api/lg/[...path]/route.ts): LANGSMITH_API_KEY.
 */

import { useEffect } from "react";

import { AGENT_INBOXES_LOCAL_STORAGE_KEY } from "@/components/agent-inbox/constants";

const BOOTSTRAP_ID = "linwood-default";

export function InboxBootstrap() {
  useEffect(() => {
    const graphId = process.env.NEXT_PUBLIC_GRAPH_ID || "deal_triage";
    const name = process.env.NEXT_PUBLIC_INBOX_NAME || "Deal Triage";

    // Absolute URL: langgraph-sdk's `new URL(path, apiUrl)` rejects relative.
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
