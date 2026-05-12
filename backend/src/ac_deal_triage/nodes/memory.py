"""Memory writer node.

On each analyst action: persist DealMemoryEntry, write LangSmith feedback,
update sponsor/broker rows, and maybe append a paragraph to the firm doc.
The deal entry write is the source of truth; everything else is best-effort.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_store
from langsmith import Client as LangSmithClient
from langsmith.run_helpers import get_current_run_tree
from pydantic import BaseModel, Field

from .. import store as store_helpers
from ..models import chat_model
from ..schemas import (
    AnalystAction,
    BrokerRecord,
    DealContext,
    DealMemoryEntry,
    Recommendation,
    SponsorRecord,
    TriageState,
    compute_reward,
)

log = logging.getLogger(__name__)

_ls = LangSmithClient()


# ---- policy-bucket rule extraction ----

FirmSection = Literal[
    "Fund mandate",
    "Asset class preferences",
    "Hard rules",
    "Soft preferences",
]


_RULE_EXTRACTION_PROMPT = """\
You maintain a real estate fund's investment-policy document.

Given:
- a deal (DealContext)
- the agent's recommendation (pursue/pass + rationale)
- the analyst's decision (pursue/pass) and free-text note

Decide whether the note implies a *generalizable* lesson about the firm's
**policy**: a new mandate clause, hard rule, asset-class preference, or
soft preference that would apply to future deals.

Lessons about a *specific sponsor* (e.g. "PLG overstated cap again") or a
*specific broker* (e.g. "Vantage RE keeps shopping junk") are NOT policy
updates; they are entity-level signals tracked separately as sponsor/broker
rows. Set `append=false` for those.

Append only when the lesson is broadly applicable across deals and entities.

When `append` is true, also pick a `section`:
  - "Fund mandate":            vehicle / check-size / geography / hold-period
  - "Asset class preferences": preferences within an asset class
  - "Hard rules":              new threshold-based hard rules
  - "Soft preferences":        anything else that's preference-level

Write `paragraph` in policy-doc voice: third person, declarative, one short
markdown paragraph. Reference the triggering deal name in parentheses.
Be conservative; set `append=false` when in doubt.
"""


class _RuleExtraction(BaseModel):
    """Structured output for the policy-rule extraction LLM call."""

    append: bool = Field(description="Does this note generalize into a firm policy update?")
    section: FirmSection | None = Field(
        default=None,
        description="Which H2 section the paragraph belongs under. Null when append=false.",
    )
    paragraph: str = Field(
        default="",
        description=(
            "If append=true, the paragraph to insert. Empty string when append=false."
        ),
    )


_rule_extractor = chat_model.with_structured_output(_RuleExtraction)


async def _maybe_extract_policy_update(
    deal: DealContext,
    reco: Recommendation,
    action: AnalystAction,
) -> _RuleExtraction | None:
    if not action.note:
        return None
    payload = {
        "deal": deal.model_dump(mode="json"),
        "agent_recommendation": reco.model_dump(mode="json"),
        "analyst_action": action.model_dump(mode="json"),
    }
    result: _RuleExtraction = await _rule_extractor.ainvoke(
        [
            SystemMessage(content=_RULE_EXTRACTION_PROMPT),
            HumanMessage(content=json.dumps(payload)),
        ]
    )
    if not result.append or not result.section or not result.paragraph.strip():
        return None
    return result


async def _apply_policy_update(store, payload: _RuleExtraction) -> None:
    assert payload.section is not None
    decorated = f"**{payload.section}**: {payload.paragraph.strip()}"
    await store_helpers.append_to_firm_memory(store, decorated)


async def _handle_policy_update(
    store,
    deal: DealContext,
    reco: Recommendation,
    action: AnalystAction,
) -> None:
    try:
        extracted = await _maybe_extract_policy_update(deal, reco, action)
        if extracted is not None:
            await _apply_policy_update(store, extracted)
    except Exception as e:  # noqa: BLE001
        log.warning("policy update failed: %s", e)


# ---- engagement updates ----
#
# Counts (n_memos, n_pursues) are deterministic. engagement_summary is
# rewritten per memo by an LLM that reads the current summary plus the
# new deal and analyst note. The LLM may no-op on routine deals.


class _SummaryUpdate(BaseModel):
    """Structured output for the engagement-summary update LLM call."""

    summary: str = Field(
        description=(
            "Updated running summary (2-4 sentences). If the new deal does "
            "not reveal or reinforce a pattern, return the current summary "
            "unchanged. Return the summary text directly, no preamble."
        )
    )


_summary_updater = chat_model.with_structured_output(_SummaryUpdate)


_ENGAGEMENT_SUMMARY_PROMPT_TEMPLATE = """\
You maintain a short running summary of how a real-estate fund has engaged \
with one specific {entity_type} ({entity_name}). The summary captures \
patterns the firm's analysts have observed (sponsor cap-rate behavior, \
sponsor bench quality, broker deal quality, IC outcomes) so the triage \
agent can apply that pattern to the next deal.

Current summary:
{current_summary_block}

New deal just reviewed:
- Deal: {deal_name}, {state}, {price}, {cap_rate}% cap
- Agent recommended: {agent_decision}
- Analyst's call: {analyst_decision}
- Analyst note: {note_block}

Decide what to do:
1. If the new deal reveals new pattern info OR strongly reinforces an \
   existing pattern (especially when the analyst left a note), update \
   the summary to reflect it. Keep it tight (2-4 sentences total).
2. If the deal is routine (no analyst note, decisions consistent with the \
   prior pattern, no new info), return the current summary unchanged.
3. If the analyst note contradicts the prior summary, replace the relevant \
   clause; don't keep stale claims.

Return only the new summary text, no preamble.
"""


def _format_summary_prompt(
    *,
    entity_type: str,
    entity_name: str,
    current_summary: str,
    deal: DealContext,
    agent_decision: str,
    analyst_decision: str,
    note: str | None,
) -> str:
    price = f"${deal.asking_price_usd:,.0f}"
    return _ENGAGEMENT_SUMMARY_PROMPT_TEMPLATE.format(
        entity_type=entity_type,
        entity_name=entity_name,
        current_summary_block=current_summary.strip()
        if current_summary.strip()
        else "(none yet; this is the first deal involving this entity)",
        deal_name=deal.deal_name,
        state=deal.location.state,
        price=price,
        cap_rate=f"{deal.cap_rate_pct:.2f}",
        agent_decision=agent_decision,
        analyst_decision=analyst_decision,
        note_block=note.strip() if note and note.strip() else "(no note left)",
    )


async def _update_engagement_summary(
    *,
    entity_type: str,
    entity_name: str,
    current_summary: str,
    deal: DealContext,
    reco: Recommendation,
    action: AnalystAction,
) -> str:
    """LLM call. On failure returns `current_summary` unchanged."""
    prompt = _format_summary_prompt(
        entity_type=entity_type,
        entity_name=entity_name,
        current_summary=current_summary,
        deal=deal,
        agent_decision=reco.decision,
        analyst_decision=action.decision,
        note=action.note,
    )
    try:
        result: _SummaryUpdate = await _summary_updater.ainvoke(
            [HumanMessage(content=prompt)]
        )
        new_summary = result.summary.strip()
        return new_summary or current_summary
    except Exception as e:  # noqa: BLE001
        log.warning(
            "engagement summary update failed for %s %s: %s",
            entity_type,
            entity_name,
            e,
        )
        return current_summary


async def _update_sponsor_engagement(
    store,
    name: str,
    deal: DealContext,
    reco: Recommendation,
    action: AnalystAction,
) -> None:
    existing = await store_helpers.get_sponsor(store, name)
    new_summary = await _update_engagement_summary(
        entity_type="sponsor",
        entity_name=name,
        current_summary=existing.engagement_summary if existing else "",
        deal=deal,
        reco=reco,
        action=action,
    )
    pursued = action.decision == "pursue"
    record = SponsorRecord(
        name=name,
        n_memos=(existing.n_memos + 1) if existing else 1,
        n_pursues=(existing.n_pursues + (1 if pursued else 0)) if existing else (1 if pursued else 0),
        engagement_summary=new_summary,
        last_updated=datetime.now(tz=timezone.utc),
    )
    await store_helpers.upsert_sponsor(store, record)


async def _update_broker_engagement(
    store,
    name: str,
    deal: DealContext,
    reco: Recommendation,
    action: AnalystAction,
) -> None:
    existing = await store_helpers.get_broker(store, name)
    new_summary = await _update_engagement_summary(
        entity_type="broker",
        entity_name=name,
        current_summary=existing.engagement_summary if existing else "",
        deal=deal,
        reco=reco,
        action=action,
    )
    pursued = action.decision == "pursue"
    record = BrokerRecord(
        name=name,
        n_memos=(existing.n_memos + 1) if existing else 1,
        n_pursues=(existing.n_pursues + (1 if pursued else 0)) if existing else (1 if pursued else 0),
        engagement_summary=new_summary,
        last_updated=datetime.now(tz=timezone.utc),
    )
    await store_helpers.upsert_broker(store, record)


# ---- LangSmith feedback ----


async def _write_feedback(
    run_id: str,
    reco: Recommendation,
    action: AnalystAction,
) -> None:
    """Two feedback rows on the trace root (categorical + numeric).

    Sync LangSmith client wrapped in asyncio.to_thread; the two writes
    fire concurrently. Failures are logged, never raised.
    """
    call = action.decision
    reward = compute_reward(reco.decision, action)

    try:
        await asyncio.gather(
            asyncio.to_thread(
                _ls.create_feedback,
                run_id=run_id,
                key="analyst_call",
                value=call,
                comment=action.note,
            ),
            asyncio.to_thread(
                _ls.create_feedback,
                run_id=run_id,
                key="reward",
                score=float(reward),
            ),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("LangSmith feedback write failed for run %s: %s", run_id, e)


# ---- node ----


def _raw_memo_from_messages(state: TriageState) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    first = messages[0]
    content = getattr(first, "content", first)
    return content if isinstance(content, str) else str(content)


async def memory_writer_node(state: TriageState) -> dict:
    reco = state.get("structured_response")
    action = state.get("analyst_action")
    if reco is None or action is None:
        raise RuntimeError("memory_writer_node called with incomplete state")

    store = get_store()

    rt = get_current_run_tree()
    run_id = str(rt.trace_id) if rt else None

    memo_id = state.get("memo_id")
    if not memo_id:
        memo_id = f"memo-{uuid.uuid4().hex[:8]}"
        log.warning("memory_writer_node: state had no memo_id; generated %s", memo_id)

    entry = DealMemoryEntry(
        memo_id=memo_id,
        deal=reco.deal,
        raw_memo=_raw_memo_from_messages(state),
        agent_recommendation=reco,
        analyst_action=action,
        run_id=run_id,
        created_at=datetime.now(tz=timezone.utc),
    )
    await store_helpers.add_deal_entry(store, entry)

    # Fan out: independent tasks, separate store namespaces / remote service.
    # return_exceptions keeps a sibling failure from cancelling the rest.
    tasks: list = []
    if run_id is not None:
        tasks.append(_write_feedback(run_id, reco, action))
    if reco.deal.sponsor:
        tasks.append(
            _update_sponsor_engagement(store, reco.deal.sponsor, reco.deal, reco, action)
        )
    if reco.deal.broker:
        tasks.append(
            _update_broker_engagement(store, reco.deal.broker, reco.deal, reco, action)
        )
    tasks.append(_handle_policy_update(store, reco.deal, reco, action))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            log.warning("memory_writer fan-out task raised: %s", r)

    return {}
