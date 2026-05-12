"use client";

import React from "react";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";

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

function DecisionChip({
  decision,
  label,
}: {
  decision: "pursue" | "pass";
  label: string;
}) {
  const cls =
    decision === "pursue"
      ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
      : "bg-gray-100 text-gray-700 ring-gray-200";
  return (
    <span
      className={`text-xs px-2 py-0.5 rounded ring-1 ring-inset font-medium ${cls}`}
    >
      {label}: {decision}
    </span>
  );
}

function Row({
  entry,
  expanded,
  onToggle,
}: {
  entry: DealMemoryEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      id={`memo-${entry.memo_id}`}
      className="border border-gray-200 rounded bg-white mb-3 overflow-hidden"
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full text-left p-5 hover:bg-gray-50/50 focus:outline-none focus:ring-2 focus:ring-orange-300 focus:ring-inset"
      >
        <div className="flex items-start gap-3">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400 shrink-0 mt-1" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400 shrink-0 mt-1" />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="font-medium text-gray-900">
                  {entry.deal.deal_name}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {entry.deal.asset_type} · {entry.deal.location.city},{" "}
                  {entry.deal.location.state} ·{" "}
                  {fmtUsd(entry.deal.asking_price_usd)} ·{" "}
                  {entry.deal.cap_rate_pct.toFixed(2)}% cap ·{" "}
                  {entry.deal.occupancy_pct.toFixed(0)}% occ
                  {entry.deal.sponsor && (
                    <> · sponsor {entry.deal.sponsor}</>
                  )}
                  {entry.deal.broker && <> · broker {entry.deal.broker}</>}
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
        </div>
      </button>

      {expanded && <ExpandedDetail entry={entry} />}
    </div>
  );
}

// Inline expansion body: full memo detail under the collapsed card header.
function ExpandedDetail({ entry }: { entry: DealMemoryEntry }) {
  return (
    <div className="border-t border-gray-100 bg-gray-50/40 px-5 py-4 space-y-5">
      <section>
        <SectionLabel>Deal facts</SectionLabel>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-2 text-sm mt-2">
          <Field label="Asset type" value={entry.deal.asset_type} />
          <Field
            label="Location"
            value={`${entry.deal.location.city}, ${entry.deal.location.state}`}
          />
          <Field
            label="Asking price"
            value={fmtUsd(entry.deal.asking_price_usd)}
          />
          <Field
            label="NOI (T-12)"
            value={fmtUsd(entry.deal.current_noi_usd)}
          />
          <Field
            label="Cap rate"
            value={`${entry.deal.cap_rate_pct.toFixed(2)}%`}
          />
          <Field
            label="Occupancy"
            value={`${entry.deal.occupancy_pct.toFixed(0)}%`}
          />
          <Field
            label="Size"
            value={`${entry.deal.size_sqft.toLocaleString()} sqft`}
          />
          <Field label="Source" value={entry.deal.source} />
          {entry.deal.sponsor && (
            <Field label="Sponsor" value={entry.deal.sponsor} />
          )}
          {entry.deal.broker && (
            <Field label="Broker" value={entry.deal.broker} />
          )}
        </div>
      </section>

      <section>
        <SectionLabel>Decisions</SectionLabel>
        <div className="mt-2 flex items-center gap-2 flex-wrap text-sm">
          <DecisionChip
            decision={entry.agent_recommendation.decision}
            label="agent"
          />
          <span className="text-gray-300">→</span>
          <DecisionChip
            decision={entry.analyst_action.decision}
            label="analyst"
          />
          {entry.agent_recommendation.decision !==
            entry.analyst_action.decision && (
            <span className="text-amber-700 bg-amber-50 ring-1 ring-amber-200 rounded-full px-2 py-0.5 text-[10px] font-medium">
              override
            </span>
          )}
          <span className="text-xs text-gray-400">
            reward {entry.reward}
          </span>
        </div>
        {entry.agent_recommendation.key_risks.length > 0 && (
          <>
            <div className="text-xs text-gray-500 mt-3">Key risks</div>
            <ul className="text-sm list-disc pl-5 text-gray-700 mt-1">
              {entry.agent_recommendation.key_risks.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section>
        <SectionLabel>Raw memo</SectionLabel>
        <pre className="mt-2 text-xs whitespace-pre-wrap font-mono bg-white border border-gray-200 rounded p-3 text-gray-700 max-h-60 overflow-y-auto">
          {entry.raw_memo || "(none captured)"}
        </pre>
      </section>

      <section className="text-xs text-gray-500 flex items-center justify-between border-t border-gray-100 pt-3">
        <span>{new Date(entry.created_at).toLocaleString()}</span>
        {entry.run_id && (
          <a
            href={`https://smith.langchain.com/o/-/projects/p/-/r/${entry.run_id}`}
            target="_blank"
            rel="noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="text-orange-700 hover:underline"
          >
            LangSmith trace ↗
          </a>
        )}
      </section>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] uppercase tracking-wide text-gray-400">
        {label}
      </span>
      <span className="text-gray-800">{value}</span>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] uppercase tracking-wide text-gray-500 font-medium">
      {children}
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
  // memo_ids currently expanded; multiple can be open at once.
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set());

  const toggle = React.useCallback((memoId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(memoId)) next.delete(memoId);
      else next.add(memoId);
      return next;
    });
  }, []);

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

  // Honor `/done#memo-<id>` deep links: auto-expand the matching row and
  // scroll to it. Runs after entries load so the DOM element exists.
  React.useEffect(() => {
    if (loading) return;
    const hash = window.location.hash;
    if (!hash.startsWith("#memo-")) return;
    const memoId = hash.slice("#memo-".length);
    if (!memoId) return;
    setExpanded((prev) => {
      if (prev.has(memoId)) return prev;
      const next = new Set(prev);
      next.add(memoId);
      return next;
    });
    requestAnimationFrame(() => {
      const el = document.getElementById(`memo-${memoId}`);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }, [loading, entries]);

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
        Completed triage. The analyst&apos;s final pursue/pass call on every
        memo, with the agent&apos;s rationale and any rejection note kept for
        the audit trail. Click a row to expand for full details.
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
            <Row
              key={e.memo_id}
              entry={e}
              expanded={expanded.has(e.memo_id)}
              onToggle={() => toggle(e.memo_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
