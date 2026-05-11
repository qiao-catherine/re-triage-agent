"""Tools the research agent calls.

Three tools, one job each:
  - extract_fields(raw_memo)         -> DealContext       (LLM extraction)
  - read_firm_memory()               -> str               (whole policy doc)
  - find_similar_deals(at, st, $)    -> list[SimilarDeal] (tiered retrieval)

`read_firm_memory` and `find_similar_deals` reach the LangGraph Store via
`get_store()` — the platform injects it per-call so tool signatures stay clean.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.config import get_store

from . import store as store_helpers
from .models import chat_model
from .schemas import AssetType, DealContext, SimilarDeal

# Bound once at import — same model object, structured to return DealContext.
_extractor = chat_model.with_structured_output(DealContext)

_EXTRACTION_SYSTEM_PROMPT = """\
You are an extraction model for a real estate investment fund's intake pipeline.
Given a raw inbound deal memo (broker forward, OM teaser, lender intro, etc.),
extract structured DealContext fields. Infer reasonable values from context
(e.g. infer state from city, infer asset_type from descriptors).

The response schema is enforced server-side — return values that conform to
the DealContext pydantic model.
"""


@tool
async def extract_fields(raw_memo: str) -> dict:
    """Extract structured DealContext fields from the raw memo text.

    Uses LangChain's structured-output binding on the shared chat_model —
    the response is server-side-validated against the DealContext schema, so
    a malformed extraction surfaces as a parse error here, not as silent
    bad JSON downstream.

    Args:
        raw_memo: The full text of the inbound memo / email / OM excerpt.

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

    Read the whole thing — it encodes mandate, hard rules, and lessons learned.
    Cite specific rule names in your reasoning where applicable.
    """
    store = get_store()
    firm = await store_helpers.read_firm_memory(store)
    return firm.doc


@tool
async def find_similar_deals(
    asset_type: AssetType,
    state: str,
    asking_price_usd: float,
) -> list[dict]:
    """Find up to 4 past deals similar to the current one.

    Filters by the three dimensions that matter for precedent: asset class,
    state, and dollar-size band. Falls back to wider criteria if too few
    matches. Each result includes the analyst's prior decision and any note
    — use these as direct precedent in your reasoning.

    Args:
        asset_type: one of the eight AssetType literals (e.g. "Multifamily").
        state: 2-letter US state code (e.g. "TX").
        asking_price_usd: the current deal's asking price; we'll look for
            past deals within ±50% of this number.
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


RESEARCH_TOOLS = [extract_fields, read_firm_memory, find_similar_deals]
