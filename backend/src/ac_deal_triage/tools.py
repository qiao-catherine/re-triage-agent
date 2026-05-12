"""Tools the triage agent calls.

  - extract_fields(raw_memo)         -> DealContext       (LLM extraction)
  - read_firm_memory()               -> str               (whole policy doc)
  - lookup_sponsor(name)             -> SponsorRecord|None
  - lookup_broker(name)              -> BrokerRecord|None
  - find_similar_deals(at, st, $)    -> list[SimilarDeal] (tiered retrieval)

Store-backed tools fetch the store via `get_store()`; the platform injects
it per-call.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.config import get_store

from . import store as store_helpers
from .models import chat_model
from .schemas import AssetType, DealContext, SimilarDeal

_extractor = chat_model.with_structured_output(DealContext)

_EXTRACTION_SYSTEM_PROMPT = """\
You are an extraction model for a real estate investment fund's intake pipeline.
Given a raw inbound deal memo (broker forward, OM teaser, lender intro, etc.),
extract structured DealContext fields. Infer reasonable values from context
(e.g. infer state from city, infer asset_type from descriptors).

Two name fields drive the firm's institutional memory; extract both verbatim
when present, null only when genuinely not named:

  - `sponsor`: the GP / operating partner (e.g. "Phoenix Logistics Group").
  - `broker`:  the brokerage firm forwarding or marketing the deal
               (e.g. "CBRE", "JLL", "Newmark"). For broker-forwarded emails
               the brokerage is in the email signature or the From-line
               domain. Use the brokerage name, not the individual agent's.

The response schema is enforced server-side; return values that conform to
the DealContext pydantic model.
"""


@tool
async def extract_fields(raw_memo: str) -> dict:
    """Extract structured DealContext fields from the raw memo text.

    Args:
        raw_memo: full text of the inbound memo / email / OM excerpt.

    Returns: a dict matching the DealContext schema.
    """
    deal: DealContext = await _extractor.ainvoke(
        [
            SystemMessage(content=_EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(content=raw_memo),
        ]
    )
    return deal.model_dump(mode="json")


@tool
async def read_firm_memory() -> str:
    """Return the firm's policy / preferences document (markdown).

    Encodes mandate, hard rules, soft preferences. Cite specific rule names
    in your reasoning where applicable.
    """
    store = get_store()
    firm = await store_helpers.read_firm_memory(store)
    return firm.doc


@tool
async def lookup_sponsor(name: str) -> dict | None:
    """Look up the firm's record on a sponsor / GP by name.

    Returns a SponsorRecord dict with:
      - `name`:               verbatim match of the key
      - `n_memos`:            total deals the firm has seen from this sponsor
      - `n_pursues`:          how many of those the analyst pursued
      - `pursue_rate_pct`:    derived percentage (n_pursues / n_memos)
      - `engagement_summary`: short running prose (2-4 sentences) on the
                              firm's qualitative observations (cap-rate
                              behavior, IC outcomes, bench quality, exits).
                              Rewritten by an LLM on each new memo.
      - `last_updated`:       ISO timestamp of last write

    Returns null when the firm has no tracked record on this sponsor; treat
    that as "no prior signal" rather than "neutral".

    How to read the values together:
      - n_memos is signal strength: 1 is anecdote, 3+ is a pattern.
      - pursue_rate_pct is direction: <=25% leans pass, >=75% leans pursue.
      - engagement_summary is the qualitative why; quote the relevant
        clause verbatim in your rationale.

    Match is by exact name. Use the sponsor name verbatim from DealContext.

    Args:
        name: Sponsor / GP name as extracted from the memo.
    """
    store = get_store()
    record = await store_helpers.get_sponsor(store, name)
    return record.model_dump(mode="json") if record else None


@tool
async def lookup_broker(name: str) -> dict | None:
    """Look up the firm's record on a broker / brokerage by name.

    Same shape as `lookup_sponsor`. `engagement_summary` covers deal quality,
    channel reliability, fit with mandate. Returns null when no record.
    Read values the same way: n_memos for strength, pursue_rate_pct for
    direction, engagement_summary for the why.

    Args:
        name: Broker / brokerage name as extracted from the memo.
    """
    store = get_store()
    record = await store_helpers.get_broker(store, name)
    return record.model_dump(mode="json") if record else None


@tool
async def find_similar_deals(
    asset_type: AssetType,
    state: str,
    asking_price_usd: float,
) -> list[dict]:
    """Find up to 4 past deals similar to the current one.

    Filters by asset class, state, and dollar-size band. Falls back to wider
    criteria if too few matches. Each result includes the analyst's prior
    decision and any note; use these as direct precedent.

    Args:
        asset_type: one of the eight AssetType literals.
        state: 2-letter US state code.
        asking_price_usd: current deal's asking price; we look within +/-50%.
    """
    store = get_store()
    similar: list[SimilarDeal] = await store_helpers.find_similar_deals(
        store,
        asset_type=asset_type,
        state=state,
        asking_price_usd=asking_price_usd,
        k=4,
    )
    return [s.model_dump(mode="json") for s in similar]


RESEARCH_TOOLS = [
    extract_fields,
    read_firm_memory,
    lookup_sponsor,
    lookup_broker,
    find_similar_deals,
]
