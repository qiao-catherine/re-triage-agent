"""Human-in-the-loop interrupt node.

Emits a HumanInterrupt payload that agent-inbox renders. The description is
markdown — the deal-memo card the analyst sees.

Response mapping (agent-inbox response type → AnalystAction):
  - "accept"   → AnalystAction(decision="accepted", note=None)
  - "response" → AnalystAction(decision="rejected", note=<text>)
  - "ignore"   → AnalystAction(decision="accepted", note=None)  (defensive)
  - "edit"     → disabled in config; raise if it arrives anyway.

Reward is NOT computed here — it's a derived field on DealMemoryEntry,
computed at write time in memory_writer_node.
"""

from __future__ import annotations

from langgraph.types import interrupt

from ..schemas import (
    AnalystAction,
    Decision,
    DealContext,
    Recommendation,
    TriageState,
    opposite,
)


def _action_title(deal: DealContext) -> str:
    """Title shown as the agent-inbox card header — names the deal so the
    inbox is scannable when several memos are pending review."""
    loc = f"{deal.location.city}, {deal.location.state}"
    return f"Review: {deal.deal_name} ({deal.asset_type}, {loc})"


def _format_card(reco: Recommendation) -> str:
    """Markdown rendering for the agent-inbox card.

    Order is intentional: recommendation first (the answer), then deal
    financials (the receipts), then cited rules and analogs (the work).
    """
    deal = reco.deal
    risks_md = (
        "\n".join(f"- {r}" for r in reco.key_risks)
        if reco.key_risks
        else "_none flagged_"
    )
    similar_md_lines = []
    for s in reco.similar_deals:
        line = (
            f"- **{s.deal_name}** ({s.asset_type}, ${s.asking_price_usd:,.0f} "
            f"@ {s.cap_rate_pct:.2f}% cap) → analyst **{s.analyst_decision}**"
        )
        if s.note:
            line += f' — _"{s.note}"_'
        similar_md_lines.append(line)
    similar_md = (
        "\n".join(similar_md_lines) if similar_md_lines else "_no analogs found_"
    )

    decision_badge = "🟢 Pursue" if reco.decision == "pursue" else "🔴 Pass"

    return f"""\
## Recommendation: {decision_badge}

**Rationale.** {reco.rationale}

**Key risks.**
{risks_md}

---

### Deal context

- **Property** — {deal.deal_name}
- **Location** — {deal.location.city}, {deal.location.state} {deal.location.zipcode}
- **Asset type** — {deal.asset_type}
- **Size** — {deal.size_sqft:,} sqft
- **Asking price** — ${deal.asking_price_usd:,.0f}
- **Current NOI** — ${deal.current_noi_usd:,.0f}
- **Cap rate** — {deal.cap_rate_pct:.2f}%
- **Occupancy** — {deal.occupancy_pct:.1f}%
- **Source** — {deal.source}

### Cited firm memory
{reco.firm_memory_excerpt}

### Similar past deals
{similar_md}
"""


def _response_to_action(
    response: dict, agent_decision: Decision
) -> AnalystAction:
    """Map an agent-inbox HumanResponse to our AnalystAction.

    AnalystAction now carries the analyst's explicit pursue/pass (not their
    relationship to the agent). Mapping rules:

      - accept / ignore → keep agent's call, no note
      - response (free text) → flip to opposite, attach the note as reasoning
      - edit → analyst opened the form, may have changed decision and/or note
    """
    rtype = response.get("type")
    args = response.get("args")

    if rtype in ("accept", "ignore"):
        return AnalystAction(decision=agent_decision, note=None)
    if rtype == "response":
        note = args if isinstance(args, str) and args.strip() else None
        return AnalystAction(decision=opposite(agent_decision), note=note)
    if rtype == "edit":
        # `args` is an ActionRequest dict: {"action": ..., "args": {decision, note}}
        edited = args.get("args", {}) if isinstance(args, dict) else {}
        raw_decision = edited.get("decision") or agent_decision
        if raw_decision not in ("pursue", "pass"):
            raise RuntimeError(
                f"edit returned invalid decision: {raw_decision!r}; expected 'pursue' or 'pass'."
            )
        raw_note = edited.get("note")
        note = (
            raw_note if isinstance(raw_note, str) and raw_note.strip() else None
        )
        return AnalystAction(decision=raw_decision, note=note)

    raise RuntimeError(
        f"Unexpected interrupt response type: {rtype!r}."
    )


async def human_review_node(state: TriageState) -> dict:
    reco = state.get("structured_response")
    if reco is None:
        raise RuntimeError(
            "human_review_node called before the triage agent produced a Recommendation"
        )

    request = {
        "action_request": {
            "action": _action_title(reco.deal),
            "args": {"decision": reco.decision, "note": ""},  # pre-filled
        },
        "config": {
            # Our forked thread-view.tsx exposes ONLY the Edit form (decision
            # toggle + note). Accept stays enabled so Studio/CLI keep working.
            "allow_accept": True,
            "allow_respond": False,
            "allow_edit": True,
            "allow_ignore": False,
        },
        "description": _format_card(reco),
    }

    response = interrupt([request])[0]
    action = _response_to_action(response, reco.decision)
    return {"analyst_action": action}
