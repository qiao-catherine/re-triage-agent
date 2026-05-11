import { Client } from "@langchain/langgraph-sdk";

/**
 * Build a LangGraph SDK client that talks to *our own* Next.js server-side
 * proxy at `/api/lg`, NOT the LangGraph deployment directly. The proxy
 * injects LANGSMITH_API_KEY from server env so the key never enters the
 * browser bundle.
 *
 * We resolve to an absolute URL (window.location.origin + "/api/lg")
 * because the SDK's internal `new URL(path, apiUrl)` rejects a relative
 * `apiUrl`. The deploymentUrl / langchainApiKey arguments are kept in the
 * signature for compatibility with the agent-inbox internals but ignored.
 */
export const createClient = (_unused?: {
  deploymentUrl?: string;
  langchainApiKey?: string | undefined;
}) => {
  const apiUrl = proxyUrl();
  return new Client({ apiUrl });
};

export function proxyUrl(): string {
  if (typeof window === "undefined") {
    // Server-side rendering: any absolute URL works since this code path
    // doesn't actually fetch. Pick a placeholder that's syntactically valid.
    return "http://localhost/api/lg";
  }
  return `${window.location.origin}/api/lg`;
}
