// Read the LangGraph Platform's long-term Store via the SDK's StoreClient.
//
// Namespaces (must match backend src/ac_deal_triage/store.py):
//   ("firm",)     key="policies"  FirmMemory
//   ("sponsors",) key=name        SponsorRecord
//   ("brokers",)  key=name        BrokerRecord
//   ("deals",)    key=memo_id     DealMemoryEntry

import { Client } from "@langchain/langgraph-sdk";

import { proxyUrl } from "./client";

const FIRM_NAMESPACE = ["firm"];
const FIRM_KEY = "policies";
const SPONSORS_NAMESPACE = ["sponsors"];
const BROKERS_NAMESPACE = ["brokers"];
const DEALS_NAMESPACE = ["deals"];

// Lazy client init so we can read window.location.origin at call time.
let _client: Client | null = null;
function client(): Client {
  if (!_client) _client = new Client({ apiUrl: proxyUrl() });
  return _client;
}

export type FirmMemory = {
  doc: string;
  updated_at: string;
};

export type DealMemoryEntry = {
  memo_id: string;
  deal: {
    deal_name: string;
    sponsor: string | null;
    broker: string | null;
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
  raw_memo: string;
  agent_recommendation: {
    decision: "pursue" | "pass";
    rationale: string;
    key_risks: string[];
  };
  analyst_action: {
    decision: "pursue" | "pass";
    note: string | null;
  };
  // Backend @computed_field, materialized into stored JSON.
  final_decision: "pursue" | "pass";
  reward: number;
  run_id: string | null;
  created_at: string;
};

export type SponsorRecord = {
  name: string;
  n_memos: number;
  n_pursues: number;
  // Backend @computed_field (n_pursues / n_memos).
  pursue_rate_pct: number;
  // Short running prose, rewritten by an LLM on each new memo.
  engagement_summary: string;
  last_updated: string;
};

// Brokers have the same wire shape as sponsors; alias keeps call sites cleaner
// and lets them diverge later.
export type BrokerRecord = SponsorRecord;

// ---- firm memory ----

export async function fetchMemory(): Promise<FirmMemory> {
  const item = await client().store.getItem(FIRM_NAMESPACE, FIRM_KEY);
  if (!item || !item.value) {
    return { doc: "_(firm memory not yet seeded)_", updated_at: new Date().toISOString() };
  }
  return item.value as FirmMemory;
}

// ---- sponsor + broker rows ----

function sortByUpdated<T extends { last_updated: string }>(records: T[]): T[] {
  return records.sort(
    (a, b) =>
      new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime(),
  );
}

export async function fetchSponsors(): Promise<SponsorRecord[]> {
  const result = await client().store.searchItems(SPONSORS_NAMESPACE, {
    limit: 200,
  });
  const records = (result.items ?? []).map((it) => it.value as SponsorRecord);
  return sortByUpdated(records);
}

export async function fetchBrokers(): Promise<BrokerRecord[]> {
  const result = await client().store.searchItems(BROKERS_NAMESPACE, {
    limit: 200,
  });
  const records = (result.items ?? []).map((it) => it.value as BrokerRecord);
  return sortByUpdated(records);
}

// ---- deal memory ----

export async function fetchInbounds(
  decision?: "pursue" | "pass",
): Promise<DealMemoryEntry[]> {
  // Filter pushes down via @computed_field materialized into the stored JSON.
  const filter =
    decision === undefined ? undefined : { final_decision: decision };

  const result = await client().store.searchItems(DEALS_NAMESPACE, {
    filter,
    limit: 200,
  });

  const entries = (result.items ?? []).map((it) => it.value as DealMemoryEntry);
  entries.sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );
  return entries;
}
