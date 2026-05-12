"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { RefreshCw } from "lucide-react";

import {
  fetchBrokers,
  fetchMemory,
  fetchSponsors,
  type BrokerRecord,
  type FirmMemory,
  type SponsorRecord,
} from "@/lib/deployment-api";
import { useFocusRefresh } from "@/lib/use-focus-refresh";

type LoadState = {
  memory: FirmMemory | null;
  sponsors: SponsorRecord[];
  brokers: BrokerRecord[];
};

export default function MemoryPage(): React.ReactNode {
  const [data, setData] = React.useState<LoadState>({
    memory: null,
    sponsors: [],
    brokers: [],
  });
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(() => {
    setLoading(true);
    Promise.all([fetchMemory(), fetchSponsors(), fetchBrokers()])
      .then(([memory, sponsors, brokers]) =>
        setData({ memory, sponsors, brokers }),
      )
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : String(e)),
      )
      .finally(() => setLoading(false));
  }, []);

  useFocusRefresh(load);

  return (
    <div className="px-8 py-10 max-w-6xl mx-auto">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-gray-900">
            Firm memory
          </h1>
          <p className="text-gray-500 mt-2 text-sm max-w-3xl leading-relaxed">
            Three layers: the policy document, sponsor records, and broker
            records. Counts update deterministically on each new deal;
            engagement summaries are short running narratives the system
            rewrites per memo, weighing the new analyst note against the
            existing summary.
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="shrink-0 text-xs px-2.5 py-1.5 rounded-md border border-gray-200 text-gray-600 hover:bg-gray-50 hover:text-gray-900 disabled:opacity-50 flex items-center gap-1.5 transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {loading && !data.memory ? (
        <div className="mt-8 text-sm text-gray-400">Loading…</div>
      ) : error ? (
        <div className="mt-8 text-sm text-gray-500">
          Couldn&apos;t load the firm memory. {error}
        </div>
      ) : (
        <div className="mt-8 space-y-10">
          <PolicySection memory={data.memory} />
          <EntitySection
            title="Sponsors"
            subtitle="Per-sponsor / per-GP engagement. The agent calls lookup_sponsor(name) on every deal."
            records={data.sponsors}
            emptyLabel="No sponsor records yet."
          />
          <EntitySection
            title="Brokers"
            subtitle="Per-broker engagement. The agent calls lookup_broker(name) when a memo names a broker."
            records={data.brokers}
            emptyLabel="No broker records yet."
          />
        </div>
      )}
    </div>
  );
}

function PolicySection({ memory }: { memory: FirmMemory | null }) {
  if (!memory) return null;
  return (
    <section>
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-base font-semibold tracking-tight text-gray-900">
          Policy document
        </h2>
        <div className="text-xs text-gray-400">
          updated {new Date(memory.updated_at).toLocaleString()}
        </div>
      </div>
      <article className="prose prose-sm max-w-none rounded-lg border border-gray-200 bg-white px-8 py-6 shadow-sm">
        {/* No rehype-raw: LLM content stays markdown, not raw HTML. */}
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{memory.doc}</ReactMarkdown>
      </article>
    </section>
  );
}

function EntitySection({
  title,
  subtitle,
  records,
  emptyLabel,
}: {
  title: string;
  subtitle: string;
  records: SponsorRecord[];
  emptyLabel: string;
}) {
  return (
    <section>
      <div className="mb-3">
        <h2 className="text-base font-semibold tracking-tight text-gray-900">
          {title}
        </h2>
        <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>
      </div>
      {records.length === 0 ? (
        <div className="text-sm text-gray-400 rounded-lg border border-dashed border-gray-200 bg-white px-6 py-8 text-center">
          {emptyLabel}
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <colgroup>
              <col className="w-[22%]" />
              <col className="w-[10%]" />
              <col className="w-[14%]" />
              <col />
            </colgroup>
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50/60 text-[11px] uppercase tracking-[0.08em] text-gray-500">
                <th className="px-5 py-3 text-left font-semibold">Name</th>
                <th className="px-5 py-3 text-right font-semibold">Memos</th>
                <th className="px-5 py-3 text-right font-semibold">
                  Pursue rate
                </th>
                <th className="px-5 py-3 text-left font-semibold">
                  Engagement summary
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {records.map((r) => (
                <EntityRow key={r.name} record={r} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function EntityRow({ record }: { record: SponsorRecord }) {
  return (
    <tr className="align-top hover:bg-gray-50/50 transition-colors">
      <td className="px-5 py-4 align-top">
        <div className="font-medium text-gray-900 leading-snug">
          {record.name}
        </div>
      </td>
      <td className="px-5 py-4 text-right tabular-nums text-gray-900 align-top">
        <span className="text-base font-medium">{record.n_memos}</span>
      </td>
      <td className="px-5 py-4 text-right align-top">
        <PursueRate
          pct={record.pursue_rate_pct}
          nMemos={record.n_memos}
          nPursues={record.n_pursues}
        />
      </td>
      <td className="px-5 py-4 text-gray-700 leading-relaxed align-top">
        {record.engagement_summary || (
          <span className="text-gray-400 italic">No summary yet.</span>
        )}
      </td>
    </tr>
  );
}

function PursueRate({
  pct,
  nMemos,
  nPursues,
}: {
  pct: number;
  nMemos: number;
  nPursues: number;
}) {
  const tone = toneFor(pct, nMemos);
  return (
    <div className="inline-flex flex-col items-end gap-1">
      <span
        className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ring-1 ring-inset tabular-nums ${tone}`}
      >
        {pct.toFixed(0)}%
      </span>
      <span className="text-[10px] text-gray-400 tabular-nums">
        {nPursues} of {nMemos}
      </span>
    </div>
  );
}

// Soft tint for the percentage chip. Interpretation lives here (and in the
// agent's head) so the data layer stays factual: no polarity field.
function toneFor(pct: number, nMemos: number): string {
  if (nMemos < 2) return "bg-gray-50 text-gray-600 ring-gray-200";
  if (pct <= 25) return "bg-rose-50 text-rose-700 ring-rose-200";
  if (pct >= 75) return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  return "bg-amber-50 text-amber-700 ring-amber-200";
}
