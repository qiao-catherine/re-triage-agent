"use client";

import React from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowLeft, ChevronDown } from "lucide-react";

import { useThreadsContext } from "./contexts/ThreadContext";
import { useQueryParams } from "./hooks/use-query-params";
import {
  IMPROPER_SCHEMA,
  VIEW_STATE_THREAD_QUERY_PARAM,
} from "./constants";
import type { ThreadData, HumanInterrupt } from "./types";
import { logger } from "./utils/logger";

type Decision = "pursue" | "pass";

type SimilarDeal = {
  memo_id: string;
  deal_name: string;
  asset_type: string;
  asking_price_usd: number;
  cap_rate_pct: number;
  analyst_decision: Decision;
  note: string | null;
};

type DealContext = {
  deal_name: string;
  sponsor?: string | null;
  broker?: string | null;
  location: { city: string; state: string; zipcode: string };
  asset_type: string;
  size_sqft: number;
  asking_price_usd: number;
  current_noi_usd: number;
  cap_rate_pct: number;
  occupancy_pct: number;
  source: string;
  triage_pod?: string;
};

type EntityContext = {
  name: string;
  n_memos: number;
  n_pursues: number;
  pursue_rate_pct: number;
  engagement_summary: string;
};

type Recommendation = {
  deal: DealContext;
  firm_memory_excerpt: string;
  similar_deals: SimilarDeal[];
  sponsor_context?: EntityContext | null;
  broker_context?: EntityContext | null;
  decision: Decision;
  rationale: string;
  key_risks: string[];
};

type MessagePart = { type?: string; text?: string };
type AnyMessage = { content?: string | MessagePart[] };

type TriageValues = {
  messages?: AnyMessage[];
  structured_response?: Recommendation;
};

// ---- formatters ------------------------------------------------------------

function fmtUsd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(n);
}

function formatLocation(loc: DealContext["location"]): string {
  const city = (loc?.city ?? "").trim();
  const state = (loc?.state ?? "").trim();
  // Portfolios spanning multiple locations come through as "Multiple, Multiple";
  // render cleanly instead of repeating the placeholder.
  const isMultiple =
    city.toLowerCase() === "multiple" || state.toLowerCase() === "multiple";
  if (isMultiple) return "Multiple locations";
  if (!city && !state) return "-";
  const zip = (loc?.zipcode ?? "").trim();
  return [city, state, zip].filter(Boolean).join(", ");
}

function firstHumanMessageContent(messages: AnyMessage[] | undefined): string {
  if (!messages || messages.length === 0) return "";
  const first = messages[0];
  if (typeof first.content === "string") return first.content;
  if (Array.isArray(first.content)) {
    return first.content
      .map((p) => (typeof p === "string" ? p : p?.text || ""))
      .join("");
  }
  return "";
}

function splitFirmMemory(excerpt: string): {
  mandate: string;
  hardRules: string;
} {
  // The firm doc's verbatim sections are headed "## Fund mandate", "## Asset
  // class preferences", "## Hard rules", etc. Split on the hard-rules header
  // so we can render them as two separate sub-sections; if no split is
  // possible, treat the whole thing as mandate.
  const lower = excerpt.toLowerCase();
  const idx = lower.indexOf("## hard rules");
  if (idx === -1) return { mandate: excerpt.trim(), hardRules: "" };
  return {
    mandate: excerpt.slice(0, idx).trim(),
    hardRules: excerpt.slice(idx).trim(),
  };
}

// ---- card subcomponents ----------------------------------------------------

function CollapsibleCard({
  title,
  defaultOpen = false,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="rounded border border-gray-200 bg-white">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-gray-50"
      >
        <span className="text-sm font-semibold text-gray-900">{title}</span>
        <ChevronDown
          className={`w-4 h-4 text-gray-500 transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>
      {open && (
        <div className="px-5 pb-5 border-t border-gray-100 pt-4">{children}</div>
      )}
    </div>
  );
}

function RecommendationCard({ reco }: { reco: Recommendation }) {
  const pursue = reco.decision === "pursue";
  return (
    <div
      className={`rounded-lg border-2 p-6 ${
        pursue
          ? "border-emerald-200 bg-emerald-50/40"
          : "border-gray-300 bg-gray-50/40"
      }`}
    >
      <div className="flex items-baseline gap-3 flex-wrap">
        <div className="text-xs uppercase tracking-wider text-gray-500 font-semibold">
          Recommendation
        </div>
        <div
          className={`text-2xl font-bold capitalize ${
            pursue ? "text-emerald-700" : "text-gray-800"
          }`}
        >
          {reco.decision}
        </div>
        {reco.deal?.triage_pod && (
          <span className="ml-auto inline-flex items-center rounded-md bg-white px-2 py-0.5 text-xs font-medium text-gray-700 ring-1 ring-inset ring-gray-200">
            Triage: {reco.deal.triage_pod}
          </span>
        )}
      </div>

      <div className="mt-4 text-sm text-gray-800 leading-relaxed">
        <span className="font-semibold">Rationale.</span> {reco.rationale}
      </div>

      {reco.key_risks && reco.key_risks.length > 0 ? (
        <div className="mt-4 text-sm text-gray-800">
          <div className="font-semibold mb-1">Key risks</div>
          <ul className="list-disc pl-5 space-y-1 text-gray-700">
            {reco.key_risks.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="mt-4 text-sm text-gray-500 italic">No risks flagged</div>
      )}
    </div>
  );
}

function DealContextRows({ deal }: { deal: DealContext }) {
  const rows: Array<[string, string]> = [
    ["Analyst triage", deal.triage_pod || "-"],
    ["Property", deal.deal_name],
    ["Sponsor", deal.sponsor || "-"],
    ["Broker", deal.broker || "-"],
    ["Location", formatLocation(deal.location)],
    ["Asset type", deal.asset_type],
    ["Size", `${(deal.size_sqft ?? 0).toLocaleString()} sqft`],
    ["Asking price", fmtUsd(deal.asking_price_usd)],
    ["Current NOI", fmtUsd(deal.current_noi_usd)],
    ["Cap rate", `${(deal.cap_rate_pct ?? 0).toFixed(2)}%`],
    ["Occupancy", `${(deal.occupancy_pct ?? 0).toFixed(0)}%`],
    ["Source", deal.source],
  ];
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
      {rows.map(([k, v]) => (
        <React.Fragment key={k}>
          <dt className="text-gray-500">{k}</dt>
          <dd className="text-gray-900">{v}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function SupportingEvidence({ excerpt }: { excerpt: string }) {
  const { mandate, hardRules } = splitFirmMemory(excerpt);
  return (
    <div className="space-y-5">
      {mandate && (
        <div>
          <div className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold mb-1">
            Fund mandate
          </div>
          <article className="prose prose-sm max-w-none text-gray-800">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{mandate}</ReactMarkdown>
          </article>
        </div>
      )}
      {hardRules && (
        <div>
          <div className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold mb-1">
            Hard rules
          </div>
          <article className="prose prose-sm max-w-none text-gray-800">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {hardRules}
            </ReactMarkdown>
          </article>
        </div>
      )}
    </div>
  );
}

function EntityContextBlock({
  label,
  ctx,
}: {
  label: string;
  ctx: EntityContext;
}) {
  const tone = toneFor(ctx.pursue_rate_pct, ctx.n_memos);
  return (
    <div className="border-l-2 border-gray-200 pl-3">
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-xs uppercase tracking-wide text-gray-500">
          {label}
        </div>
        <span
          className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset tabular-nums ${tone}`}
        >
          {ctx.pursue_rate_pct.toFixed(0)}%
        </span>
      </div>
      <div className="text-sm font-medium text-gray-900 mt-0.5">
        {ctx.name}
      </div>
      <div className="text-xs text-gray-500 mt-0.5 tabular-nums">
        {ctx.n_memos} memo{ctx.n_memos === 1 ? "" : "s"} ·{" "}
        {ctx.n_pursues}/{ctx.n_memos} pursued
      </div>
      {ctx.engagement_summary && (
        <div className="text-sm text-gray-700 mt-2 leading-relaxed">
          {ctx.engagement_summary}
        </div>
      )}
    </div>
  );
}

function toneFor(pct: number, nMemos: number): string {
  if (nMemos < 2) return "bg-gray-100 text-gray-600 ring-gray-200";
  if (pct <= 25) return "bg-rose-50 text-rose-700 ring-rose-200";
  if (pct >= 75) return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  return "bg-amber-50 text-amber-700 ring-amber-200";
}

function SimilarDealsList({ deals }: { deals: SimilarDeal[] }) {
  if (deals.length === 0)
    return <div className="text-sm text-gray-500 italic">No analogs found</div>;
  return (
    <ul className="space-y-2 text-sm text-gray-800">
      {deals.map((s) => (
        <li key={s.memo_id} className="border-l-2 border-gray-200 pl-3">
          <div className="font-medium">{s.deal_name}</div>
          <div className="text-xs text-gray-500">
            {s.asset_type} · {fmtUsd(s.asking_price_usd)} ·{" "}
            {s.cap_rate_pct.toFixed(2)}% cap · analyst{" "}
            <span className="font-medium capitalize">{s.analyst_decision}</span>
          </div>
          {s.note && (
            <div className="text-xs italic text-gray-600 mt-1">
              &ldquo;{s.note}&rdquo;
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

// ---- main view -------------------------------------------------------------

export function ThreadView<
  TV extends Record<string, any> = Record<string, any>,
>({ threadId }: { threadId: string }) {
  const router = useRouter();
  const { updateQueryParams } = useQueryParams();
  const {
    threadData: threads,
    loading,
    sendHumanResponse,
    fetchThreads,
  } = useThreadsContext<TV>();

  const [threadData, setThreadData] =
    React.useState<ThreadData<TV>>();
  const [decision, setDecision] = React.useState<Decision>("pursue");
  const [note, setNote] = React.useState("");
  const [submitting, setSubmitting] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    try {
      if (typeof window === "undefined") return;
      if (!threadId || !threads.length || loading) return;
      const selected = threads.find((t) => t.thread.thread_id === threadId);
      if (!selected) {
        updateQueryParams(VIEW_STATE_THREAD_QUERY_PARAM);
        return;
      }
      setThreadData(selected);
      const interrupt = (selected.interrupts ?? [])[0] as
        | HumanInterrupt
        | undefined;
      const args = (interrupt?.action_request?.args ?? {}) as Record<
        string,
        unknown
      >;
      if (args.decision === "pursue" || args.decision === "pass") {
        setDecision(args.decision);
      }
    } catch (e) {
      logger.error("Error setting thread data", e);
    }
  }, [threads, loading, threadId, updateQueryParams]);

  React.useEffect(() => {
    if (typeof window !== "undefined") window.scrollTo(0, 0);
  }, []);

  if (!threadData) return null;

  const interrupt = (threadData.interrupts ?? [])[0] as
    | HumanInterrupt
    | undefined;
  const title =
    interrupt?.action_request?.action &&
    interrupt.action_request.action !== IMPROPER_SCHEMA
      ? interrupt.action_request.action
      : `Thread: ${threadData.thread.thread_id.slice(0, 6)}…`;

  // Read structured state set by the triage agent's response_format.
  const values = (threadData.thread.values ?? {}) as TriageValues;
  const reco = values.structured_response;
  const rawMemo = firstHumanMessageContent(values.messages);

  async function onSubmit() {
    if (!threadData || !interrupt) return;
    setErr(null);
    setSubmitting(true);
    try {
      const result = sendHumanResponse(threadData.thread.thread_id, [
        {
          type: "edit",
          args: {
            action: interrupt.action_request.action,
            args: { decision, note: note.trim() },
          },
        },
      ]);
      if (result && typeof (result as Promise<unknown>).then === "function") {
        await (result as Promise<unknown>);
      }
      await fetchThreads("interrupted");
      router.push("/");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="px-8 py-6 max-w-7xl mx-auto w-full">
      <button
        onClick={() => router.push("/")}
        className="text-gray-500 hover:text-gray-900 mb-4 flex items-center gap-1 text-sm"
      >
        <ArrowLeft className="w-4 h-4" /> Back
      </button>

      <h1 className="text-2xl font-semibold text-gray-900 mb-6 leading-tight">
        {title}
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {reco ? (
            <>
              <RecommendationCard reco={reco} />

              <CollapsibleCard title="Deal context" defaultOpen>
                <DealContextRows deal={reco.deal} />
              </CollapsibleCard>

              {reco.firm_memory_excerpt && (
                <CollapsibleCard title="Supporting evidence">
                  <SupportingEvidence excerpt={reco.firm_memory_excerpt} />
                </CollapsibleCard>
              )}

              {(reco.sponsor_context || reco.broker_context) && (
                <CollapsibleCard
                  title="Past engagement on sponsor / broker"
                  defaultOpen
                >
                  <div className="space-y-4">
                    {reco.sponsor_context && (
                      <EntityContextBlock
                        label="Sponsor"
                        ctx={reco.sponsor_context}
                      />
                    )}
                    {reco.broker_context && (
                      <EntityContextBlock
                        label="Broker"
                        ctx={reco.broker_context}
                      />
                    )}
                  </div>
                </CollapsibleCard>
              )}

              {reco.similar_deals && reco.similar_deals.length > 0 && (
                <CollapsibleCard title="Similar past deals">
                  <SimilarDealsList deals={reco.similar_deals} />
                </CollapsibleCard>
              )}
            </>
          ) : (
            <div className="text-sm text-gray-500 italic p-4 border border-gray-200 rounded">
              No structured recommendation in state yet.
            </div>
          )}

          {rawMemo && (
            <CollapsibleCard title="Original message">
              <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono">
                {rawMemo}
              </pre>
            </CollapsibleCard>
          )}
        </div>

        <aside className="lg:col-span-1 rounded border border-gray-200 bg-white p-6 h-fit lg:sticky lg:top-6">
          <h3 className="text-sm font-semibold text-gray-900 mb-3">
            Your decision
          </h3>

          <div className="flex gap-2 mb-4">
            {(["pursue", "pass"] as const).map((d) => {
              const active = decision === d;
              return (
                <button
                  key={d}
                  onClick={() => setDecision(d)}
                  disabled={submitting}
                  className={`flex-1 px-3 py-2 rounded border text-sm font-medium capitalize transition ${
                    active
                      ? "bg-orange-500 text-white border-orange-500"
                      : "bg-white text-gray-700 border-gray-200 hover:bg-gray-50"
                  } disabled:opacity-50`}
                >
                  {d}
                </button>
              );
            })}
          </div>

          <label className="block text-xs font-medium text-gray-600 mb-1">
            Note <span className="text-gray-400">(optional)</span>
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            disabled={submitting}
            placeholder="Why are you making this call?"
            rows={4}
            className="w-full text-sm px-3 py-2 rounded border border-gray-200 focus:outline-none focus:ring-2 focus:ring-orange-200 disabled:opacity-50"
          />

          <button
            onClick={onSubmit}
            disabled={submitting}
            className="mt-4 w-full px-3 py-2 rounded bg-orange-500 text-white text-sm font-semibold hover:bg-orange-600 disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit"}
          </button>

          {err && <div className="mt-3 text-xs text-red-500">Error: {err}</div>}
        </aside>
      </div>
    </div>
  );
}
