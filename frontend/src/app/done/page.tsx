"use client";

import React from "react";

import { RefreshCw } from "lucide-react";

import {
  fetchInbounds,
  type DealMemoryEntry,
} from "@/lib/deployment-api";

type Filter = "all" | "pursue" | "pass";

function fmtUsd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function DecisionPill({ decision }: { decision: "pursue" | "pass" }) {
  const cls =
    decision === "pursue"
      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
      : "bg-gray-100 text-gray-700 border border-gray-200";
  return (
    <span
      className={`text-xs px-2 py-1 rounded font-medium capitalize ${cls}`}
    >
      {decision}
    </span>
  );
}

function Row({ entry }: { entry: DealMemoryEntry }) {
  return (
    <div className="border border-gray-200 rounded bg-white p-5 mb-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="font-medium text-gray-900">{entry.deal.deal_name}</div>
          <div className="text-xs text-gray-500 mt-0.5">
            {entry.deal.asset_type} · {entry.deal.location.city},{" "}
            {entry.deal.location.state} · {fmtUsd(entry.deal.asking_price_usd)}{" "}
            · {entry.deal.cap_rate_pct.toFixed(2)}% cap ·{" "}
            {entry.deal.occupancy_pct.toFixed(0)}% occ
          </div>
        </div>
        <DecisionPill decision={entry.final_decision} />
      </div>

      <div className="text-sm mt-3 text-gray-800">
        <span className="text-gray-500">Rationale.</span>{" "}
        {entry.agent_recommendation.rationale}
      </div>

      {entry.analyst_action.note && (
        <div className="text-sm mt-2 italic text-gray-600">
          Analyst note: &ldquo;{entry.analyst_action.note}&rdquo;
        </div>
      )}
    </div>
  );
}

const FILTERS: { label: string; value: Filter }[] = [
  { label: "All", value: "all" },
  { label: "Pursue", value: "pursue" },
  { label: "Pass", value: "pass" },
];

export default function DonePage(): React.ReactNode {
  const [filter, setFilter] = React.useState<Filter>("all");
  const [entries, setEntries] = React.useState<DealMemoryEntry[]>([]);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(() => {
    setLoading(true);
    const decision = filter === "all" ? undefined : filter;
    fetchInbounds(decision)
      .then((es) => setEntries(es))
      .catch(() => setEntries([]))
      .finally(() => setLoading(false));
  }, [filter]);

  // Initial + filter-change fetch
  React.useEffect(() => {
    load();
  }, [load]);

  // Refetch on window focus so switching back from agent-inbox/Studio shows fresh data.
  React.useEffect(() => {
    const handler = () => load();
    window.addEventListener("focus", handler);
    return () => window.removeEventListener("focus", handler);
  }, [load]);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-gray-900">Done</h1>
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
      <p className="text-gray-500 mt-2 text-sm">
        Completed triage — the analyst&apos;s final pursue/pass call on every
        memo, with the agent&apos;s rationale and any rejection note kept for
        the audit trail.
      </p>

      <div className="mt-4 flex gap-2">
        {FILTERS.map((f) => {
          const active = filter === f.value;
          return (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`text-sm px-3 py-1.5 rounded border ${
                active
                  ? "bg-orange-500 text-white border-orange-500"
                  : "bg-white border-gray-200 text-gray-600 hover:text-gray-900"
              }`}
            >
              {f.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="text-sm text-gray-400 mt-6">Loading…</div>
      ) : entries.length === 0 ? (
        <div className="text-sm text-gray-500 mt-6">
          No completed deals for this filter.
        </div>
      ) : (
        <div className="mt-4">
          {entries.map((e) => (
            <Row key={e.memo_id} entry={e} />
          ))}
        </div>
      )}
    </div>
  );
}
