"""Human-in-the-loop interrupt node.

Emits a HumanInterrupt payload for agent-inbox to render. The description
field is markdown (the deal-memo card the analyst sees).

Response mapping (agent-inbox response type to AnalystAction):
  - "accept":   keep agent's call, no note
  - "response": flip to opposite, attach note text
  - "ignore":   keep agent's call, no note (defensive)
  - "edit":     analyst may have changed decision and/or note
"""

from __future__ import annotations

from langgraph.types import interrupt

from ..schemas import (
    AnalystAction,
    Decision,
    DealContext,
    EntityContext,
    Recommendation,
    TriageState,
    opposite,
)


def _action_title(deal: DealContext) -> str:
    loc = f"{deal.location.city}, {deal.location.state}"
    return f"Review: {deal.deal_name} ({deal.asset_type}, {loc})"


def _format_entity_block(label: str, ctx: EntityContext | None) -> str:
    if ctx is None:
        return f"**{label}.** _no record_"
    return (
        f"**{label}: {ctx.name}** "
        f"({ctx.n_memos} memo{'s' if ctx.n_memos != 1 else ''}, "
        f"{ctx.n_pursues}/{ctx.n_memos} pursued, "
        f"{ctx.pursue_rate_pct:.0f}% rate)\n\n"
        f"{ctx.engagement_summary}"
    )


def _format_card(reco: Recommendation) -> str:
    """Markdown card for agent-inbox. Recommendation, then receipts, then work."""
    deal = reco.deal
    risks_md = (
        "\n".join(f"- {r}" for r in reco.key_risks)
        if reco.key_risks
        else "_none flagged_"
    )
    similar_md_lines = []
    for s in reco.similar_deals:
        sponsor_bit = f", sponsor _{s.sponsor}_" if s.sponsor else ""
        line = (
            f"- **{s.deal_name}**{sponsor_bit} "
            f"({s.asset_type}, ${s.asking_price_usd:,.0f} "
            f"@ {s.cap_rate_pct:.2f}% cap), analyst **{s.analyst_decision}**"
        )
        if s.note:
            line += f' ("_{s.note}_")'
        similar_md_lines.append(line)
    similar_md = (
        "\n".join(similar_md_lines) if similar_md_lines else "_no analogs found_"
    )

    entity_blocks = []
    if reco.sponsor_context is not None:
        entity_blocks.append(_format_entity_block("Sponsor", reco.sponsor_context))
    if reco.broker_context is not None:
        entity_blocks.append(_format_entity_block("Broker", reco.broker_context))
    firm_record_md = (
        "\n\n".join(entity_blocks)
        if entity_blocks
        else "_no entity records returned by lookup_sponsor / lookup_broker_"
    )

    decision_badge = "🟢 Pursue" if reco.decision == "pursue" else "🔴 Pass"

    return f"""\
## Recommendation: {decision_badge}

**Rationale.** {reco.rationale}

**Key risks.**
{risks_md}

---

### Deal context

- **Property:** {deal.deal_name}
- **Sponsor:** {deal.sponsor or "_unknown_"}
- **Location:** {deal.location.city}, {deal.location.state} {deal.location.zipcode}
- **Asset type:** {deal.asset_type}
- **Size:** {deal.size_sqft:,} sqft
- **Asking price:** ${deal.asking_price_usd:,.0f}
- **Current NOI:** ${deal.current_noi_usd:,.0f}
- **Cap rate:** {deal.cap_rate_pct:.2f}%
- **Occupancy:** {deal.occupancy_pct:.1f}%
- **Source:** {deal.source}

### Cited firm memory
{reco.firm_memory_excerpt}

### Past engagement on sponsor / broker
{firm_record_md}

### Similar past deals
{similar_md}
"""


def _response_to_action(
    response: dict, agent_decision: Decision
) -> AnalystAction:
    rtype = response.get("type")
    args = response.get("args")

    if rtype in ("accept", "ignore"):
        return AnalystAction(decision=agent_decision, note=None)
    if rtype == "response":
        note = args if isinstance(args, str) and args.strip() else None
        return AnalystAction(decision=opposite(agent_decision), note=note)
    if rtype == "edit":
        # args is an ActionRequest dict: {"action": ..., "args": {decision, note}}
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

    raise RuntimeError(f"Unexpected interrupt response type: {rtype!r}.")


async def human_review_node(state: TriageState) -> dict:
    reco = state.get("structured_response")
    if reco is None:
        raise RuntimeError(
            "human_review_node called before the triage agent produced a Recommendation"
        )

    request = {
        "action_request": {
            "action": _action_title(reco.deal),
            "args": {"decision": reco.decision, "note": ""},
        },
        "config": {
            # Forked thread-view.tsx exposes only the Edit form; Accept stays
            # enabled so Studio/CLI keep working.
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
