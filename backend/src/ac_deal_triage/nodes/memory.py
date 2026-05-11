"""Memory writer node — the loop that makes the system compound.

Three jobs per analyst action:
  1. Append a DealMemoryEntry (always).
  2. Write two LangSmith feedback rows to the original trace (always, when
     `run_id` is available):
        - "analyst_call"  → categorical "pursue"/"pass" (the analyst's effective call)
        - "reward"        → numeric 0/1 (did agent's call align with analyst's)
  3. If the analyst left a note, ask the LLM whether the note generalizes
     into a firm policy. If yes, append a paragraph to firm memory.

Feedback writes are best-effort — the deal entry is the source of truth, so
its write must succeed even if LangSmith is unreachable.

The firm-memory append is the visible "compounding" step: every analyst note
that carries a generalizable lesson grows the doc that the research agent
reads on every future call.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_store
from langsmith import Client as LangSmithClient
from langsmith.run_helpers import get_current_run_tree
from pydantic import BaseModel, Field

from .. import store as store_helpers
from ..models import chat_model
from ..schemas import (
    AnalystAction,
    DealContext,
    DealMemoryEntry,
    Recommendation,
    TriageState,
    compute_reward,
)

log = logging.getLogger(__name__)

# Shared LangSmith client. Reads LANGSMITH_API_KEY from env; no-ops if unset.
_ls = LangSmithClient()


# ---- rule extraction ------------------------------------------------------

_RULE_EXTRACTION_PROMPT = """\
You maintain a real estate fund's investment-policy document.

Given:
- a deal (DealContext)
- the agent's recommendation (pursue/pass + rationale)
- the analyst's decision (accepted/rejected) and free-text note

Decide whether the note implies a *generalizable* lesson worth adding to the
firm policy doc. Generalizable means it would apply to future deals beyond
this specific property — a new rule, a refined preference, an exception to
an existing rule, or a softening/hardening of a threshold.

When `append` is true, write `paragraph` in policy-doc voice: third person,
declarative, one short markdown paragraph. Reference the triggering deal
name in parentheses with today's date.

Be conservative — set `append` to false if the note is just an idiosyncratic
comment about this one deal.
"""


class _RuleExtraction(BaseModel):
    """Structured output for the rule-extraction LLM call."""

    append: bool = Field(description="Should we append a policy paragraph?")
    paragraph: str = Field(
        default="",
        description=(
            "If append=true, the paragraph to append (markdown, policy-doc voice). "
            "Empty string when append=false."
        ),
    )


_rule_extractor = chat_model.with_structured_output(_RuleExtraction)


async def _maybe_extract_rule(
    deal: DealContext,
    reco: Recommendation,
    action: AnalystAction,
) -> str | None:
    if not action.note:
        log.info("rule extraction skipped: no analyst note")
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
    log.info(
        "rule extraction: append=%s paragraph_len=%d",
        result.append,
        len(result.paragraph or ""),
    )
    if not result.append:
        return None
    para = result.paragraph.strip()
    return para or None


# ---- LangSmith feedback ----------------------------------------------------


async def _write_feedback(
    run_id: str,
    reco: Recommendation,
    action: AnalystAction,
) -> None:
    """Two feedback rows on the trace root — categorical + numeric.

    `analyst_call` carries the analyst's effective pursue/pass and any note
    text (eval datasets / classification metrics).
    `reward` carries the 0/1 alignment signal (RL reward shaping / regression
    metrics).

    Best-effort — failures are logged, never raised. The deal entry write is
    the source of truth. Uses the async `acreate_feedback` so the LangSmith
    HTTP call doesn't block the asyncio event loop.
    """
    call = action.decision  # analyst's explicit pursue/pass
    reward = compute_reward(reco.decision, action)

    try:
        # langsmith.Client only has sync `create_feedback`; offload to a
        # thread so the asyncio event loop isn't blocked on the HTTPS call.
        await asyncio.to_thread(
            _ls.create_feedback,
            run_id=run_id,
            key="analyst_call",
            value=call,
            comment=action.note,
        )
        await asyncio.to_thread(
            _ls.create_feedback,
            run_id=run_id,
            key="reward",
            score=float(reward),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("LangSmith feedback write failed for run %s: %s", run_id, e)


# ---- node -----------------------------------------------------------------


def _raw_memo_from_messages(state: TriageState) -> str:
    """Pull the original memo text out of the first HumanMessage in state."""
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

    # Fetch the LangSmith trace root at the point of use. The trace exists
    # for the whole graph invocation, so fetching it here yields the same
    # UUID as fetching it earlier — but state stays cleaner.
    rt = get_current_run_tree()
    run_id = str(rt.trace_id) if rt else None

    # 1. Deal entry .
    memo_id = state.get("memo_id")
    if not memo_id:
        memo_id = f"memo-{uuid.uuid4().hex[:8]}"
        log.warning(
            "memory_writer_node: state had no memo_id; generated %s", memo_id
        )

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

    # 2. LangSmith feedback 
    if run_id is not None:
        await _write_feedback(run_id, reco, action)

    # 3. Firm-memory append if the analyst's note generalizes into policy.
    paragraph = await _maybe_extract_rule(reco.deal, reco, action)
    if paragraph:
        await store_helpers.append_to_firm_memory(store, paragraph)

    return {}
