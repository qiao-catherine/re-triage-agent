"""Typed schemas for the deal triage graph."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field, computed_field


# ---- enums ----

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

# Analyst triage pod: region x asset-class. Production routing would
# dispatch each memo to the matching analyst pod's inbox; in the demo
# it's a label that lets us show the routing decision.
TriagePod = Literal[
    "West / Industrial",
    "West / Multifamily",
    "West / Other",
    "Central / Industrial",
    "Central / Multifamily",
    "Central / Other",
    "East / Industrial",
    "East / Multifamily",
    "East / Other",
]


# ---- core data shapes ----


class Location(BaseModel):
    city: str = Field(description='City. "Multiple" for portfolios spanning cities.')
    state: str = Field(description='Two-letter US state code (e.g. "TX"). "Multiple" for portfolios.')
    zipcode: str = Field(description="Five-digit US zipcode; empty string if not in the memo.")


class DealContext(BaseModel):
    """Extracted from the raw memo by the research agent.

    Field order matches the agent-inbox card render order.
    """

    deal_name: str = Field(description="Property or deal name (verbatim).")
    sponsor: str | None = Field(
        default=None,
        description="Sponsor / GP name (verbatim). Null if not named in the memo.",
    )
    broker: str | None = Field(
        default=None,
        description=(
            "Broker or brokerage firm name (verbatim, e.g. 'CBRE', 'JLL', "
            "'Newmark'). Null if the memo doesn't name a broker."
        ),
    )
    location: Location = Field(
        description=(
            "City, state, and zipcode. Infer state from city when unambiguous. "
            'For multi-asset portfolios, set city and state to "Multiple".'
        )
    )
    asset_type: AssetType = Field(
        description=(
            "Closest matching AssetType literal. Default to Other only if none "
            "of the named classes fit."
        )
    )
    size_sqft: int = Field(description="Total rentable square feet.")
    asking_price_usd: float = Field(description="Asking / target acquisition price, USD.")
    current_noi_usd: float = Field(description="T-12 or in-place NOI, USD.")
    cap_rate_pct: float = Field(description="Asking cap rate, percent.")
    occupancy_pct: float = Field(description="Current occupancy, percent.")
    source: Source = Field(
        description="How the memo arrived: Broker, Owner, Lender, Partner, or Referral."
    )
    triage_pod: TriagePod = Field(
        description=(
            'Analyst triage label: "<Region> / <Class>". '
            "Region by US geography: "
            "West (CA, OR, WA, NV, AZ, UT, ID, MT, WY, CO, NM, AK, HI), "
            "Central (TX, OK, KS, NE, SD, ND, MN, IA, MO, AR, LA, WI, IL, IN, MI, OH, KY, TN), "
            "East (everything else). "
            'Class collapses asset_type: "Industrial" iff Industrial, '
            '"Multifamily" iff Multifamily, "Other" for everything else. '
            'For multi-state portfolios pick the region of the largest asset; '
            'when state is "Multiple" with no anchor, default to East.'
        )
    )


class SimilarDeal(BaseModel):
    """Slim view of a past deal returned by find_similar_deals."""

    memo_id: str
    deal_name: str
    sponsor: str | None = None
    asset_type: AssetType
    asking_price_usd: float
    cap_rate_pct: float
    analyst_decision: Decision
    note: str | None = None


class EntityContext(BaseModel):
    """Slim snapshot of a SponsorRecord/BrokerRecord for the agent's output.

    Carries the firm's record on a named sponsor or broker through state and
    out to the analyst inbox. The agent copies the lookup_sponsor /
    lookup_broker tool output verbatim into this shape.
    """

    name: str
    n_memos: int
    n_pursues: int
    pursue_rate_pct: float
    engagement_summary: str


class Recommendation(BaseModel):
    """The triage agent's complete structured output.

    Used as `response_format=` on a single create_agent call so the agent IS
    the graph node; no wrapper needed.
    """

    # evidence
    deal: DealContext = Field(
        description="Structured fields extracted from the raw memo."
    )
    firm_memory_excerpt: str = Field(
        description=(
            "Verbatim excerpt of the firm policy doc, the sections that apply "
            "to this deal. Quote rule names exactly; do not paraphrase."
        )
    )
    similar_deals: list[SimilarDeal] = Field(
        default_factory=list,
        description="Up to 4 precedents from find_similar_deals.",
    )
    sponsor_context: EntityContext | None = Field(
        default=None,
        description=(
            "Verbatim copy of the lookup_sponsor tool output (slimmed to "
            "EntityContext shape). Null if the deal does not name a sponsor "
            "or the firm has no record on this sponsor."
        ),
    )
    broker_context: EntityContext | None = Field(
        default=None,
        description=(
            "Verbatim copy of the lookup_broker tool output. Null if the "
            "deal does not name a broker or the firm has no record."
        ),
    )

    # conclusion
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
    """The analyst's pursue/pass call, with an optional note.

    Posted back from agent-inbox via the interrupt resume. Same domain as
    `agent_recommendation.decision`.
    """

    decision: Decision
    note: str | None = None


def compute_reward(agent_decision: Decision, action: AnalystAction) -> int:
    """1 iff the agent's pursue/pass matched the analyst's."""
    return int(agent_decision == action.decision)


def opposite(decision: Decision) -> Decision:
    return "pass" if decision == "pursue" else "pursue"


# ---- persisted memory shapes ----


class SponsorRecord(BaseModel):
    """Sponsor row. Stored at namespace=("sponsors",), key=sponsor name.

    Counts (n_memos, n_pursues) update deterministically per memo;
    engagement_summary is rewritten by an LLM per memo.
    """

    name: str
    n_memos: int = Field(default=0, description="Total memos involving this sponsor.")
    n_pursues: int = Field(
        default=0, description="How many of those memos the analyst pursued."
    )
    engagement_summary: str = Field(
        default="",
        description="Short running prose (2-4 sentences). LLM-maintained per memo.",
    )
    last_updated: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pursue_rate_pct(self) -> float:
        if self.n_memos == 0:
            return 0.0
        return round(100.0 * self.n_pursues / self.n_memos, 1)


class BrokerRecord(BaseModel):
    """Broker row. Same shape as SponsorRecord, separate class for future fields."""

    name: str
    n_memos: int = 0
    n_pursues: int = 0
    engagement_summary: str = ""
    last_updated: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pursue_rate_pct(self) -> float:
        if self.n_memos == 0:
            return 0.0
        return round(100.0 * self.n_pursues / self.n_memos, 1)


class FirmMemory(BaseModel):
    """Firm policy doc. Stored at namespace=("firm",), key="policies"."""

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
        description="LangSmith trace root run UUID; joins this entry to the agent run.",
    )
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def final_decision(self) -> Decision:
        """Analyst's pursue/pass call. Exposed as computed field for store filters."""
        return self.analyst_action.decision

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reward(self) -> int:
        return compute_reward(self.agent_recommendation.decision, self.analyst_action)


# ---- graph state ----


class TriageState(TypedDict, total=False):
    """State threaded through the graph.

    The triage agent is a graph node directly, so state uses the agent's
    natural I/O shape: `messages` in, `structured_response` out.
    """

    messages: Annotated[list[AnyMessage], add_messages]
    memo_id: str
    structured_response: Recommendation | None
    analyst_action: AnalystAction | None
