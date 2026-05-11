"""Typed schemas for the deal triage graph.

Everything that crosses a node boundary, gets persisted, or shows up in the
HumanInterrupt payload is defined here. Keep this file dependency-light.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, computed_field


# ---- enums ------------------------------------------------------------------

AssetType = Literal[
    "Multifamily",
    "Office",
    "Retail",
    "Industrial",
    "Hospitality",
    "Mixed-Use",
    "Land",
    "Other",
]

Source = Literal["Broker", "Owner", "Lender", "Partner", "Referral"]

Decision = Literal["pursue", "pass"]


# ---- core data shapes -------------------------------------------------------


class Location(BaseModel):
    city: str
    state: str
    zipcode: str


class DealContext(BaseModel):
    """Extracted from the raw memo by the research agent.

    Field order is the order it renders in the agent-inbox card — keep the
    money fields together so the analyst can scan the financials in one row.
    """

    deal_name: str = Field(description="Property or deal name; identifies the opportunity.")
    location: Location
    asset_type: AssetType
    size_sqft: int = Field(description="Total rentable square footage.")
    asking_price_usd: float = Field(description="Main valuation anchor.")
    current_noi_usd: float = Field(description="Current income basis.")
    cap_rate_pct: float = Field(description="Quick pricing / yield metric.")
    occupancy_pct: float = Field(description="Stabilization and leasing risk indicator.")
    source: Source = Field(description="How the memo arrived at the firm.")


class SimilarDeal(BaseModel):
    """Slim view of a past deal returned by find_similar_deals."""

    memo_id: str
    deal_name: str
    asset_type: AssetType
    asking_price_usd: float
    cap_rate_pct: float
    analyst_decision: Decision
    note: str | None = None


class Recommendation(BaseModel):
    """The triage agent's complete structured output.

    Combines evidence (deal extraction, firm-memory excerpt, similar past
    deals — gathered via the three tools) and conclusion (decision, rationale,
    key risks). Designed to be `response_format=` on a single create_agent
    call so the agent IS the graph node — no wrapper needed.
    """

    # ---- evidence (gathered via tools) -----------------------------------
    deal: DealContext = Field(
        description="Structured fields extracted from the raw memo."
    )
    firm_memory_excerpt: str = Field(
        description=(
            "Verbatim excerpt of the firm policy doc — the sections that apply "
            "to this deal. Quote rule names exactly; do not paraphrase."
        )
    )
    similar_deals: list[SimilarDeal] = Field(
        default_factory=list,
        description="Up to 4 precedents from find_similar_deals.",
    )

    # ---- conclusion (synthesized) ----------------------------------------
    decision: Decision = Field(description='"pursue" or "pass".')
    rationale: str = Field(
        description=(
            "1-3 sentences. Cite (a) specific deal numbers, (b) at least one "
            "firm rule by exact name from firm_memory_excerpt, and (c) at least "
            "one similar past deal when any are returned."
        )
    )
    key_risks: list[str] = Field(
        default_factory=list,
        description="1-3 concrete risks (numbers, dates, names) worth diligence.",
    )


class AnalystAction(BaseModel):
    """The analyst's pursue/pass call on the deal, with an optional note.

    Posted back from agent-inbox via the interrupt resume. `decision` is the
    analyst's *own* call (not relative to the agent) — same domain as
    `agent_recommendation.decision`.
    """

    decision: Decision
    note: str | None = None


def compute_reward(agent_decision: Decision, action: AnalystAction) -> int:
    """Reward = 1 iff the agent's pursue/pass matched the analyst's pursue/pass.

    Single source of truth for reward computation. Used by both the
    DealMemoryEntry @computed_field and the LangSmith feedback writer.
    """
    return int(agent_decision == action.decision)


def opposite(decision: Decision) -> Decision:
    """The other pursue/pass — useful when mapping agent-inbox 'response'
    (analyst disagrees) to the analyst's explicit call."""
    return "pass" if decision == "pursue" else "pursue"


# ---- persisted memory shapes -----------------------------------------------


class FirmMemory(BaseModel):
    """One growing markdown document. Stored at namespace=("firm",), key="policies".

    Intentionally minimal — `updated_at` is enough to convey "this doc is alive
    and growing" for the UI. No revision counter; if audit history is ever
    needed, back it with an actual append-only log keyed by revision id.
    """

    doc: str
    updated_at: datetime


class DealMemoryEntry(BaseModel):
    """One past deal. Stored at namespace=("deals",), key=memo_id."""

    memo_id: str
    deal: DealContext
    raw_memo: str
    agent_recommendation: Recommendation
    analyst_action: AnalystAction
    run_id: str | None = Field(
        default=None,
        description=(
            "LangSmith trace root run UUID — joins this entry to the agent run "
            "that produced the recommendation. Used to write analyst feedback "
            "back onto the original trace via `Client.create_feedback`."
        ),
    )
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def final_decision(self) -> Decision:
        """The analyst's pursue/pass call — what happens to the deal.

        Now trivially equals `analyst_action.decision` (since AnalystAction
        carries pursue/pass directly), but exposed as a computed field for
        backward compatibility with store filters keyed on `final_decision`.
        """
        return self.analyst_action.decision

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reward(self) -> int:
        """1 iff agent's pursue/pass matched the analyst's pursue/pass.

        Derived — never accepted as input, never stored as a separate
        source of truth. Always consistent with `agent_recommendation`
        and `analyst_action` by construction.
        """
        return compute_reward(self.agent_recommendation.decision, self.analyst_action)


# ---- graph state ------------------------------------------------------------


class TriageState(TypedDict, total=False):
    """State threaded through the LangGraph graph.

    The triage agent is added directly as a node (no wrapper), so state has
    the agent's natural I/O shape:
      - `messages` — input HumanMessage(raw_memo) lands here
      - `structured_response` — the agent's parsed Recommendation lands here

    Other notes:
      - `reward` is NOT in state — it's a @computed_field on DealMemoryEntry,
        derived from agent_recommendation + analyst_action at write time.
      - `run_id` (LangSmith trace root) is NOT threaded through state either —
        memory_writer_node fetches it at the point of use via
        `get_current_run_tree()`. The trace root exists for the entire graph
        invocation, so fetching it later gives the same UUID.
      - `raw_memo` was dropped — memory_writer extracts it from
        `messages[0].content` when writing DealMemoryEntry.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    memo_id: str
    structured_response: Recommendation | None
    analyst_action: AnalystAction | None
