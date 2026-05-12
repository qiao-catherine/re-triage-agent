import { Client } from "@langchain/langgraph-sdk";

/**
 * Build a LangGraph SDK client that talks to our Next.js proxy at `/api/lg`,
 * not the LangGraph deployment directly. The proxy injects LANGSMITH_API_KEY
 * from server env so the key never enters the browser bundle.
 *
 * The arguments are kept in the signature for compat with the agent-inbox
 * internals but ignored.
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
    // SSR: any syntactically valid absolute URL works; this path doesn't fetch.
    return "http://localhost/api/lg";
  }
  return `${window.location.origin}/api/lg`;
}
