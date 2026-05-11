// Read from the LangGraph Platform's built-in long-term Store.
//
// We hit the platform's standard /store endpoints (via the SDK's StoreClient)
// rather than maintaining custom /memory and /inbounds routes that read from
// a parallel InMemoryStore. The platform's store is the single source of truth:
// the graph nodes write deals and policy paragraphs to it via langgraph.config
// `get_store()`, and the frontend reads them straight back from the same
// store via the platform's API.
//
// Namespaces (must match what `src/ac_deal_triage/store.py` uses on the
// backend):
//   ("firm",)   key="policies"        → FirmMemory (one doc)
//   ("deals",)  key=memo_id            → DealMemoryEntry (one per deal)

import { Client } from "@langchain/langgraph-sdk";

import { proxyUrl } from "./client";

const FIRM_NAMESPACE = ["firm"];
const FIRM_KEY = "policies";
const DEALS_NAMESPACE = ["deals"];

// Lazily build the client on first use so we can read window.location.origin
// — the SDK's internal `new URL(path, apiUrl)` rejects a relative apiUrl.
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
    location: { city: string; state: string; zipcode: string };
    asset_type: string;
    size_sqft: number;
    asking_price_usd: number;
    current_noi_usd: number;
    cap_rate_pct: number;
    occupancy_pct: number;
    source: string;
  };
  raw_memo: string;
  agent_recommendation: {
    decision: "pursue" | "pass";
    rationale: string;
    key_risks: string[];
  };
  analyst_action: {
    // Analyst's explicit pursue/pass call (not "accepted/rejected" relative
    // to the agent — that's derivable as analyst_action.decision == agent_recommendation.decision).
    decision: "pursue" | "pass";
    note: string | null;
  };
  // Derived on the backend (@computed_field) — the analyst's final pursue/pass call.
  final_decision: "pursue" | "pass";
  reward: number;
  run_id: string | null;
  created_at: string;
};

// ---- firm memory -----------------------------------------------------------

export async function fetchMemory(): Promise<FirmMemory> {
  const item = await client().store.getItem(FIRM_NAMESPACE, FIRM_KEY);
  if (!item || !item.value) {
    // Store may not have been seeded yet — return an empty doc rather than throw.
    return { doc: "_(firm memory not yet seeded)_", updated_at: new Date().toISOString() };
  }
  return item.value as FirmMemory;
}

// ---- deal memory -----------------------------------------------------------

export async function fetchInbounds(
  decision?: "pursue" | "pass",
): Promise<DealMemoryEntry[]> {

  // Filter on `final_decision` (the analyst's effective pursue/pass), which
  // is a pydantic @computed_field materialized into the stored JSON.
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
