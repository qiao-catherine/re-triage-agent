"""Thin wrapper over the LangGraph Store for our two namespaces.

Namespaces:
  ("firm",)   — single key "policies" holding the FirmMemory doc
  ("deals",)  — key=memo_id, holding DealMemoryEntry rows

Everything async because that's what the deployment store exposes. Locally we
get the same API via InMemoryStore — see `seed_store_if_empty`.

Similarity is intentionally minimal (asset_type filter + recency sort) so
reviewers can read it. Production swap-in is a vector index over the deal
+ rationale text at the same seam.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.store.base import BaseStore

from .schemas import (
    Decision,
    DealMemoryEntry,
    FirmMemory,
    SimilarDeal,
)
from .seed import HISTORICAL_DEALS, INITIAL_FIRM_DOC

FIRM_NS = ("firm",)
FIRM_KEY = "policies"
DEALS_NS = ("deals",)


# ---- firm memory -----------------------------------------------------------


async def read_firm_memory(store: BaseStore) -> FirmMemory:
    item = await store.aget(FIRM_NS, FIRM_KEY)
    if item is None:
        # Lazy-seed on first read so the deployment doesn't need a setup script.
        firm = FirmMemory(
            doc=INITIAL_FIRM_DOC,
            updated_at=datetime.now(tz=timezone.utc),
        )
        await store.aput(FIRM_NS, FIRM_KEY, firm.model_dump(mode="json"))
        return firm
    return FirmMemory.model_validate(item.value)


async def append_to_firm_memory(store: BaseStore, paragraph: str) -> FirmMemory:
    """Append a paragraph to the firm doc.

    Read-modify-write on a single store row. Not an append-only log; if you
    need revision history, back it with a separate `("firm", "revisions")`
    namespace keyed by timestamp.
    """
    current = await read_firm_memory(store)
    new_doc = current.doc.rstrip() + "\n\n" + paragraph.strip() + "\n"
    updated = FirmMemory(
        doc=new_doc,
        updated_at=datetime.now(tz=timezone.utc),
    )
    await store.aput(FIRM_NS, FIRM_KEY, updated.model_dump(mode="json"))
    return updated


# ---- deal memory -----------------------------------------------------------


async def add_deal_entry(store: BaseStore, entry: DealMemoryEntry) -> None:
    """Upsert a deal entry. If `memo_id` already exists, the row is overwritten.

    Each memo is triaged once in our flow, so this is fine. If a memo can be
    re-triaged (e.g. analyst flips a decision later), use a compound key
    `(memo_id, run_id)` instead.
    """
    await store.aput(DEALS_NS, entry.memo_id, entry.model_dump(mode="json"))


async def list_deal_entries(
    store: BaseStore,
    *,
    decision: Decision | None = None,
    limit: int = 200,
) -> list[DealMemoryEntry]:
    """List deal entries, optionally filtered by the analyst's final pursue/pass.

    `final_decision` is the @computed_field on DealMemoryEntry that captures
    the analyst's effective call. It's materialized into the stored JSON at
    write time, so we can push the filter to the store backend.
    """
    filter_arg = {"final_decision": decision} if decision is not None else None
    items = await store.asearch(DEALS_NS, filter=filter_arg, limit=limit)
    entries = [DealMemoryEntry.model_validate(it.value) for it in items]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries


# ---- similarity ------------------------------------------------------------


async def find_similar_deals(
    store: BaseStore,
    *,
    asset_type: str,
    state: str,
    asking_price_usd: float,
    k: int = 4,
) -> list[SimilarDeal]:
    """Tiered retrieval — take narrowest matches first, widen to fill up to k.

    Tiers (most → least specific):
      1. same asset_type + state + price within ±50%
      2. same asset_type + state (drop price)
      3. same asset_type (drop geo)
      4. most recent overall (drop everything)

    For each tier we fetch matching deals sorted by recency, then append to
    the result set, deduping by memo_id. Stop as soon as we have k.

    Price is a range so we over-fetch and narrow in Python — the store
    doesn't expose >= operators. Production swap-in (vector retrieval over
    deal + rationale text) drops in at this seam.
    """
    PRICE_LOW = asking_price_usd * 0.5
    PRICE_HIGH = asking_price_usd * 1.5
    # Over-fetch generously — the store returns items in insertion order, not by
    # recency, so a tight limit silently drops the deals we want.
    OVERFETCH = 200

    async def _entries(filter_arg: dict | None) -> list[DealMemoryEntry]:
        items = await store.asearch(DEALS_NS, filter=filter_arg, limit=OVERFETCH)
        es = [DealMemoryEntry.model_validate(it.value) for it in items]
        es.sort(key=lambda e: e.created_at, reverse=True)
        return es

    by_type_state = await _entries(
        {"deal": {"asset_type": asset_type, "location": {"state": state}}}
    )
    by_type = await _entries({"deal": {"asset_type": asset_type}})
    by_any = await _entries(None)

    tiers = [
        [e for e in by_type_state if PRICE_LOW <= e.deal.asking_price_usd <= PRICE_HIGH],
        by_type_state,
        by_type,
        by_any,
    ]

    selected: list[DealMemoryEntry] = []
    seen: set[str] = set()
    for tier in tiers:
        for e in tier:
            if e.memo_id in seen:
                continue
            selected.append(e)
            seen.add(e.memo_id)
            if len(selected) >= k:
                break
        if len(selected) >= k:
            break

    return [
        SimilarDeal(
            memo_id=e.memo_id,
            deal_name=e.deal.deal_name,
            asset_type=e.deal.asset_type,
            asking_price_usd=e.deal.asking_price_usd,
            cap_rate_pct=e.deal.cap_rate_pct,
            analyst_decision=e.analyst_action.decision,
            note=e.analyst_action.note,
        )
        for e in selected[:k]
    ]


# ---- one-time seeding -----------------------------------------------------


async def seed_store_if_empty(store: BaseStore) -> dict[str, int]:
    """Idempotent: populate firm doc + historical deals if not already present.

    Called from the routes app's lifespan hook, so a freshly-deployed
    instance has data to demo against. Returns a small count summary.
    """
    await read_firm_memory(store)  # lazy-seeds the firm doc if missing

    existing = await store.asearch(DEALS_NS, limit=1)
    if not existing:
        for entry in HISTORICAL_DEALS:
            await add_deal_entry(store, entry)

    deal_count = len(await store.asearch(DEALS_NS, limit=500))
    return {"deals": deal_count}
