"""LangGraph Store helpers.

Namespaces:
  ("firm",)     key="policies"  FirmMemory doc
  ("sponsors",) key=name        SponsorRecord
  ("brokers",)  key=name        BrokerRecord
  ("deals",)    key=memo_id     DealMemoryEntry

All async (deployment store is async; InMemoryStore mirrors the API).
"""

from __future__ import annotations

from datetime import datetime, timezone

from langgraph.store.base import BaseStore

from .schemas import (
    BrokerRecord,
    Decision,
    DealMemoryEntry,
    FirmMemory,
    SimilarDeal,
    SponsorRecord,
)
from .seed import HISTORICAL_DEALS, INITIAL_FIRM_DOC

FIRM_NS = ("firm",)
FIRM_KEY = "policies"
DEALS_NS = ("deals",)
SPONSORS_NS = ("sponsors",)
BROKERS_NS = ("brokers",)


# ---- firm memory ----


async def read_firm_memory(store: BaseStore) -> FirmMemory:
    item = await store.aget(FIRM_NS, FIRM_KEY)
    if item is None:
        firm = FirmMemory(
            doc=INITIAL_FIRM_DOC,
            updated_at=datetime.now(tz=timezone.utc),
        )
        await store.aput(FIRM_NS, FIRM_KEY, firm.model_dump(mode="json"))
        return firm
    return FirmMemory.model_validate(item.value)


async def append_to_firm_memory(store: BaseStore, paragraph: str) -> FirmMemory:
    """Read-modify-write a paragraph onto the firm doc."""
    current = await read_firm_memory(store)
    new_doc = current.doc.rstrip() + "\n\n" + paragraph.strip() + "\n"
    updated = FirmMemory(
        doc=new_doc,
        updated_at=datetime.now(tz=timezone.utc),
    )
    await store.aput(FIRM_NS, FIRM_KEY, updated.model_dump(mode="json"))
    return updated


# ---- deal memory ----


async def add_deal_entry(store: BaseStore, entry: DealMemoryEntry) -> None:
    """Upsert by memo_id. Each memo is triaged once in our flow."""
    await store.aput(DEALS_NS, entry.memo_id, entry.model_dump(mode="json"))


async def list_deal_entries(
    store: BaseStore,
    *,
    decision: Decision | None = None,
    limit: int = 200,
) -> list[DealMemoryEntry]:
    """List deal entries, optionally filtered by analyst's pursue/pass.

    `final_decision` is a @computed_field materialized into stored JSON,
    so the filter pushes down to the store backend.
    """
    filter_arg = {"final_decision": decision} if decision is not None else None
    items = await store.asearch(DEALS_NS, filter=filter_arg, limit=limit)
    entries = [DealMemoryEntry.model_validate(it.value) for it in items]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries


# ---- sponsor + broker memory ----


async def get_sponsor(store: BaseStore, name: str) -> SponsorRecord | None:
    item = await store.aget(SPONSORS_NS, name)
    if item is None:
        return None
    return SponsorRecord.model_validate(item.value)


async def upsert_sponsor(store: BaseStore, record: SponsorRecord) -> None:
    await store.aput(SPONSORS_NS, record.name, record.model_dump(mode="json"))


async def list_sponsors(store: BaseStore, *, limit: int = 200) -> list[SponsorRecord]:
    items = await store.asearch(SPONSORS_NS, limit=limit)
    records = [SponsorRecord.model_validate(it.value) for it in items]
    records.sort(key=lambda r: r.last_updated, reverse=True)
    return records


async def get_broker(store: BaseStore, name: str) -> BrokerRecord | None:
    item = await store.aget(BROKERS_NS, name)
    if item is None:
        return None
    return BrokerRecord.model_validate(item.value)


async def upsert_broker(store: BaseStore, record: BrokerRecord) -> None:
    await store.aput(BROKERS_NS, record.name, record.model_dump(mode="json"))


async def list_brokers(store: BaseStore, *, limit: int = 200) -> list[BrokerRecord]:
    items = await store.asearch(BROKERS_NS, limit=limit)
    records = [BrokerRecord.model_validate(it.value) for it in items]
    records.sort(key=lambda r: r.last_updated, reverse=True)
    return records


# ---- similarity ----


async def find_similar_deals(
    store: BaseStore,
    *,
    asset_type: str,
    state: str,
    asking_price_usd: float,
    k: int = 4,
) -> list[SimilarDeal]:
    """Tiered retrieval, narrowest matches first, widening to fill up to k.

    Tiers, most to least specific:
      1. asset_type + state + price within +/-50%
      2. asset_type + state
      3. asset_type
      4. most recent overall

    Production swap-in (vector retrieval over deal + rationale text) drops
    in at this seam.
    """
    PRICE_LOW = asking_price_usd * 0.5
    PRICE_HIGH = asking_price_usd * 1.5
    # Over-fetch: store returns insertion order, not recency.
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
            sponsor=e.deal.sponsor,
            asset_type=e.deal.asset_type,
            asking_price_usd=e.deal.asking_price_usd,
            cap_rate_pct=e.deal.cap_rate_pct,
            analyst_decision=e.analyst_action.decision,
            note=e.analyst_action.note,
        )
        for e in selected[:k]
    ]


# ---- one-time seeding ----


async def seed_store_if_empty(store: BaseStore) -> dict[str, int]:
    """Idempotent: populate firm doc + historical deals if missing."""
    await read_firm_memory(store)  # lazy-seeds the firm doc if missing

    existing = await store.asearch(DEALS_NS, limit=1)
    if not existing:
        for entry in HISTORICAL_DEALS:
            await add_deal_entry(store, entry)

    deal_count = len(await store.asearch(DEALS_NS, limit=500))
    return {"deals": deal_count}
