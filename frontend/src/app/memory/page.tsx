"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { RefreshCw } from "lucide-react";

import { fetchMemory, type FirmMemory } from "@/lib/deployment-api";
import { useFocusRefresh } from "@/lib/use-focus-refresh";

export default function MemoryPage(): React.ReactNode {
  const [memory, setMemory] = React.useState<FirmMemory | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(() => {
    setLoading(true);
    fetchMemory()
      .then((m) => setMemory(m))
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e)),
      )
      .finally(() => setLoading(false));
  }, []);

  useFocusRefresh(load);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">
          Firm memory
        </h1>
        <div className="flex items-center gap-3">
          {memory && (
            <div className="text-xs text-gray-500">
              updated {new Date(memory.updated_at).toLocaleString()}
            </div>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50 flex items-center gap-1"
            title="Refresh"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>
      <p className="text-gray-500 mt-2 text-sm">
        Single growing document. The research agent reads this on every triage
        call. Every analyst note that generalizes gets appended.
      </p>

      {loading && !memory ? (
        <div className="mt-6 text-sm text-gray-400">Loading…</div>
      ) : error ? (
        <div className="mt-6 text-sm text-gray-500">
          Couldn&apos;t load the firm memory. {error}
        </div>
      ) : memory ? (
        <article className="prose prose-sm max-w-none mt-6 rounded border border-gray-200 bg-white p-6">
          {/* No rehype-raw — LLM-generated content stays markdown-only, not raw HTML. */}
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{memory.doc}</ReactMarkdown>
        </article>
      ) : null}
    </div>
  );
}
