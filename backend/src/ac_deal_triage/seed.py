"""Seed corpus for the demo.

Two things live here:
  - `INITIAL_FIRM_DOC`: the firm-policy markdown the agent reads on day 1
  - `HISTORICAL_DEALS`: 20 past DealMemoryEntry records for find_similar_deals
                       to retrieve as precedent

Everything is fake. Real customer would replace with their own policy doc
and historical IC decisions. See MOCKS.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .schemas import (
    AnalystAction,
    DealContext,
    DealMemoryEntry,
    Location,
    Recommendation,
)


# ---- firm policy document (markdown) ---------------------------------------

INITIAL_FIRM_DOC = """\
# Northbrook Capital — Investment Policy

_Last updated: 2026-04-02_

## Fund mandate
- Active vehicles: **Fund IV** (value-add equity, $25M–$150M check) and **Bridge Credit I** (senior bridge debt, $15M–$60M).
- Geography: Top-50 MSAs only. CBD-adjacent submarkets preferred.
- Hold period: 4–7 years (equity); 18–36 months (bridge).

## Asset class preferences
- **Multifamily**: primary focus. 150+ units, B/B+ assets in growth MSAs (Sun Belt, Mountain West).
- **Industrial**: last-mile and shallow-bay only. Avoid big-box distribution > 500k sqft.
- **Retail**: grocery-anchored or daily-needs only. No power centers.
- **Office**: only Class A trophy assets in NYC, SF, Boston, DC. Hard pass otherwise.
- **Hospitality / Land**: out of mandate.

## Hard rules
- **No tertiary-market industrial under $50M.** (Adopted 2024-Q4 after the Toledo deal underperformed; tertiary industrial without rail/port adjacency does not clear hurdle rates at this check size.)
- **Cap rate floor: 5.0%** for stabilized assets in primary markets, **5.75%** in secondary.
- **Occupancy floor: 85%** at acquisition unless the value-add thesis is leasing-driven and explicitly underwritten.
- **Sponsor diligence**: minimum 2 prior exits in the same asset class within the last 7 years.

## Soft preferences
- Prefer broker-sourced deals from existing relationships (CBRE, JLL, Newmark capital markets teams).
- Prefer assumable debt > 4.5% in current rate environment.
- Be wary of seller-credit "earn-outs" tied to lease-up — these have historically slipped 9–12 months past underwriting.
"""


# ---- historical deals (precedent for find_similar_deals) ------------------


def _ago(days: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


def _entry(
    memo_id: str,
    deal_name: str,
    city: str,
    state: str,
    zipcode: str,
    asset_type: str,
    size_sqft: int,
    asking: float,
    noi: float,
    cap: float,
    occ: float,
    source: str,
    agent_decision: str,    # what the agent recommended
    rationale: str,
    risks: list[str],
    analyst_call: str,      # what the analyst's final pursue/pass call was
    note: str | None,
    days_ago: int,
) -> DealMemoryEntry:
    """Construct one seeded DealMemoryEntry.

    `agent_decision` and `analyst_call` are both pursue/pass — same domain.
    If they differ, the analyst overrode the agent; the reward computed_field
    on DealMemoryEntry picks that up automatically (1 if they match, else 0).
    """
    return DealMemoryEntry(
        memo_id=memo_id,
        deal=DealContext(
            deal_name=deal_name,
            location=Location(city=city, state=state, zipcode=zipcode),
            asset_type=asset_type,  # type: ignore[arg-type]
            size_sqft=size_sqft,
            asking_price_usd=asking,
            current_noi_usd=noi,
            cap_rate_pct=cap,
            occupancy_pct=occ,
            source=source,  # type: ignore[arg-type]
        ),
        raw_memo=f"[seeded historical record for {deal_name}]",
        agent_recommendation=Recommendation(
            deal=DealContext(  # snapshot of the deal as seen by the agent
                deal_name=deal_name,
                location=Location(city=city, state=state, zipcode=zipcode),
                asset_type=asset_type,  # type: ignore[arg-type]
                size_sqft=size_sqft,
                asking_price_usd=asking,
                current_noi_usd=noi,
                cap_rate_pct=cap,
                occupancy_pct=occ,
                source=source,  # type: ignore[arg-type]
            ),
            firm_memory_excerpt="",
            similar_deals=[],
            decision=agent_decision,  # type: ignore[arg-type]
            rationale=rationale,
            key_risks=risks,
        ),
        analyst_action=AnalystAction(
            decision=analyst_call,  # type: ignore[arg-type]
            note=note,
        ),
        created_at=_ago(days_ago),
    )


HISTORICAL_DEALS: list[DealMemoryEntry] = [
    # --- multifamily, mostly pursued ----------------------------------------
    _entry("hist-001", "Briar Creek Apartments", "Charlotte", "NC", "28210", "Multifamily",
           240_000, 62_000_000, 3_700_000, 5.97, 93.0, "Broker",
           "pursue", "5.97% cap on a 240-unit Class B in Charlotte; sponsor has 5 prior MF exits.",
           ["Roof capex ~$1.1M deferred"], "pursue", None, 380),
    _entry("hist-002", "Sunridge Heights", "Phoenix", "AZ", "85016", "Multifamily",
           198_000, 54_000_000, 3_080_000, 5.70, 91.5, "Broker",
           "pursue", "Sun Belt MF in mandate, 5.70% cap clears primary-market floor.",
           ["Phoenix concession environment elevated"], "pursue", None, 320),
    _entry("hist-003", "Lakeside Commons", "Tampa", "FL", "33606", "Multifamily",
           165_000, 39_500_000, 2_300_000, 5.82, 88.0, "Broker",
           "pursue", "Tampa Class B+, sponsor has 3 prior FL exits.",
           ["Insurance cost trajectory"], "pursue", None, 295),
    _entry("hist-004", "Willow Bend", "Nashville", "TN", "37013", "Multifamily",
           220_000, 58_000_000, 3_300_000, 5.69, 90.0, "Broker",
           "pursue", "Nashville growth MSA, in-line with mandate.",
           [], "pursue", None, 240),
    _entry("hist-005", "Highland Park Residences", "Denver", "CO", "80205", "Multifamily",
           180_000, 51_000_000, 2_750_000, 5.39, 92.0, "Broker",
           "pursue", "Denver MF, cap rate slightly thin but submarket trending.",
           ["Cap rate at primary-market floor"], "pursue", "tight on cap, watch.", 210),
    _entry("hist-006", "Maple Vista", "Atlanta", "GA", "30309", "Multifamily",
           160_000, 42_000_000, 2_350_000, 5.60, 87.0, "Broker",
           "pursue", "Midtown Atlanta, value-add story credible.",
           [], "pursue", None, 165),
    # --- multifamily — passes (cap too thin or sponsor weak) -----------------
    _entry("hist-007", "Crystal Springs Tower", "Miami", "FL", "33131", "Multifamily",
           320_000, 145_000_000, 6_100_000, 4.21, 95.0, "Broker",
           "pass", "Sub-5% cap in Miami; trades below mandate floor.",
           ["Cap rate below 5.0% floor"], "pass", None, 340),
    _entry("hist-008", "Cedar Grove", "Sacramento", "CA", "95816", "Multifamily",
           140_000, 36_000_000, 1_900_000, 5.28, 84.0, "Broker",
           "pass", "Occupancy below 85% floor; sponsor has only one prior CA exit.",
           ["Sponsor track record thin"], "pass", None, 280),
    # --- industrial ---------------------------------------------------------
    _entry("hist-009", "Crossroads Logistics Center", "Dallas", "TX", "75061", "Industrial",
           420_000, 78_000_000, 4_550_000, 5.83, 100.0, "Broker",
           "pursue", "Last-mile DFW, full lease, mandate fit.",
           ["WALT 4.2 yrs"], "pursue", None, 360),
    _entry("hist-010", "Toledo Logistics Park", "Toledo", "OH", "43611", "Industrial",
           380_000, 34_000_000, 2_550_000, 7.50, 100.0, "Owner",
           "pass",
           "Tertiary-market industrial under $50M — outside hard rule. Toledo deal underperformed in 2024.",
           ["Tertiary market", "No rail adjacency"], "pass",
           "this is exactly the deal we wrote the rule for.", 220),
    _entry("hist-011", "Rivergate Distribution", "Indianapolis", "IN", "46241", "Industrial",
           280_000, 56_000_000, 3_300_000, 5.89, 100.0, "Broker",
           "pursue", "Indy is top-50 MSA, shallow-bay last-mile fits.",
           [], "pursue", None, 175),
    _entry("hist-012", "Big Sky Distribution", "Billings", "MT", "59101", "Industrial",
           620_000, 88_000_000, 6_400_000, 7.27, 100.0, "Broker",
           "pass", "Out-of-mandate big-box (>500k sqft) and tertiary geography.",
           ["Big-box format", "Geography"], "pass", None, 130),
    # --- office -------------------------------------------------------------
    _entry("hist-013", "One Liberty Center", "New York", "NY", "10005", "Office",
           480_000, 295_000_000, 13_500_000, 4.58, 88.0, "Broker",
           "pursue", "FiDi trophy office, mandate-allowed market.",
           ["Tenant rollover 2027"], "pursue", None, 400),
    _entry("hist-014", "Crescent Tower", "Charlotte", "NC", "28202", "Office",
           260_000, 78_000_000, 4_400_000, 5.64, 80.0, "Broker",
           "pass", "Office outside NYC/SF/BOS/DC mandate; hard pass per policy.",
           [], "pass", None, 290),
    # Analyst overrode the agent on this one — pursued despite occupancy floor.
    _entry("hist-015", "Pacific Heights Plaza", "San Francisco", "CA", "94104", "Office",
           310_000, 165_000_000, 7_200_000, 4.36, 72.0, "Broker",
           "pass", "Below 85% occupancy floor; lease-up risk too high in current SF market.",
           ["Occupancy 72%"], "pursue",
           "disagree — at this basis the lease-up risk is priced in. push for diligence.", 180),
    # --- retail -------------------------------------------------------------
    _entry("hist-016", "Northgate Plaza", "Raleigh", "NC", "27604", "Retail",
           160_000, 38_000_000, 2_280_000, 6.00, 95.0, "Broker",
           "pursue", "Grocery-anchored (Publix), daily-needs co-tenants.",
           [], "pursue", None, 250),
    _entry("hist-017", "Crossroads Power Center", "Houston", "TX", "77024", "Retail",
           480_000, 92_000_000, 5_600_000, 6.09, 90.0, "Broker",
           "pass", "Power center format outside retail mandate.",
           ["Format"], "pass", None, 200),
    _entry("hist-018", "Brookside Village", "Salt Lake City", "UT", "84111", "Retail",
           120_000, 31_500_000, 1_980_000, 6.29, 97.0, "Broker",
           "pursue", "Daily-needs anchored, strong SLC submarket.",
           [], "pursue", None, 95),
    # --- credit deals -------------------------------------------------------
    _entry("hist-019", "Maple Ridge Bridge", "Charlotte", "NC", "28269", "Multifamily",
           200_000, 38_000_000, 2_280_000, 6.00, 91.0, "Lender",
           "pursue", "Senior bridge on Class B MF, sponsor solid.",
           ["Refi assumption rates"], "pursue", None, 70),
    # Analyst overrode the agent — Cleveland IS top-50 MSA, rule needs updating.
    _entry("hist-020", "Lakefront Bridge", "Cleveland", "OH", "44113", "Multifamily",
           175_000, 22_000_000, 1_550_000, 7.05, 86.0, "Lender",
           "pass", "Cleveland is outside top-50 MSA preference; bridge basis stretched.",
           ["Geography"], "pursue",
           "Cleveland is top-50 MSA — let's revisit and update the rule.", 45),
]


__all__ = ["INITIAL_FIRM_DOC", "HISTORICAL_DEALS"]
