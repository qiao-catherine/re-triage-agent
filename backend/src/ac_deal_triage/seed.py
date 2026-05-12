"""Seed corpus for the demo.

Customer: Linwood Capital, $8B AUM real-estate investment platform.
Asset focus: industrial + multifamily.

  - INITIAL_FIRM_DOC: firm-policy markdown (mandate, hard rules, soft prefs).
  - INITIAL_SPONSORS / INITIAL_BROKERS: structured entity rows.
  - HISTORICAL_DEALS: ~20 past DealMemoryEntry records for find_similar_deals.

Demo storyline rests on three sponsor patterns visible in HISTORICAL_DEALS:
PLG (3 cap-overstatement passes), CEP (3 IC deaths + 1 large-check pursue),
Halcyon (2 strong pursues).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .schemas import (
    AnalystAction,
    BrokerRecord,
    DealContext,
    DealMemoryEntry,
    Location,
    Recommendation,
    SponsorRecord,
)


# ---- firm policy document (markdown) ----

INITIAL_FIRM_DOC = """\
# Linwood Capital, Investment Policy

_Last updated: 2026-04-02_

## Fund mandate
- ~$8B AUM real-estate investment platform. Two active vehicles:
  **Fund V** (value-add equity, $20M to $120M check) and
  **Bridge Credit II** (senior bridge debt, $15M to $60M).
- Geography: Top-50 MSAs. Sun Belt and Mountain West preferred for
  multifamily; major logistics corridors (DFW, Inland Empire, Atlanta,
  Indianapolis, Columbus, Phoenix, etc.) for industrial.
- Hold period: 4 to 7 years (equity); 18 to 36 months (bridge).
- Target deal-flow split: 50% industrial, 35% multifamily, 15% other.

## Asset class preferences
- **Industrial**: primary focus. Last-mile and shallow-bay only. Avoid
  big-box distribution > 500k sqft and tertiary geographies.
- **Multifamily**: primary focus. 150+ unit Class B/B+ in growth MSAs.
- **Office**: Class A trophy only in NYC, SF, Boston, DC. Hard pass
  otherwise.
- **Retail**: grocery-anchored or daily-needs only. No power centers,
  no enclosed malls.
- **Mixed-use**: case-by-case; only if 60%+ of NOI is from a preferred
  asset class above.

## Hard rules
- **No tertiary-market industrial under $50M.** Adopted 2024-Q4 after
  the Toledo deal underperformed; tertiary industrial without rail/port
  adjacency does not clear hurdle rates at this check size.
- **Cap rate floor: 5.0%** for stabilized assets in primary markets,
  **5.75%** in secondary.
- **Occupancy floor: 85%** at acquisition unless the value-add thesis
  is leasing-driven and explicitly underwritten.
- **Sponsor diligence**: minimum 2 prior exits in the same asset class
  within the last 7 years.

## Soft preferences
- Prefer assumable debt > 4.5% in current rate environment.
- Be wary of seller-credit "earn-outs" tied to lease-up; these have
  historically slipped 9 to 12 months past underwriting.

## Sponsor & broker tracking
Per-sponsor and per-broker patterns are tracked as structured rows in
the firm's memory store, not paragraphs in this document. Use
`lookup_sponsor(name)` and `lookup_broker(name)` to fetch the firm's
record on a named entity. Each row carries memo counts, pursue rate,
and a running engagement summary.
"""


# ---- historical deals (precedent for find_similar_deals) ----


def _ago(days: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


def _entry(
    memo_id: str,
    deal_name: str,
    sponsor: str | None,
    broker: str | None,
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
    agent_decision: str,
    rationale: str,
    risks: list[str],
    analyst_call: str,
    note: str | None,
    days_ago: int,
) -> DealMemoryEntry:
    deal = DealContext(
        deal_name=deal_name,
        sponsor=sponsor,
        broker=broker,
        location=Location(city=city, state=state, zipcode=zipcode),
        asset_type=asset_type,  # type: ignore[arg-type]
        size_sqft=size_sqft,
        asking_price_usd=asking,
        current_noi_usd=noi,
        cap_rate_pct=cap,
        occupancy_pct=occ,
        source=source,  # type: ignore[arg-type]
    )
    return DealMemoryEntry(
        memo_id=memo_id,
        deal=deal,
        raw_memo=f"[seeded historical record for {deal_name}]",
        agent_recommendation=Recommendation(
            deal=deal,
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
    # Pattern 1: Phoenix Logistics Group, cap-rate overstaters
    _entry("hist-plg-01", "Desert Bay Distribution Center", "Phoenix Logistics Group", "CBRE",
           "Phoenix", "AZ", "85043", "Industrial",
           320_000, 64_000_000, 3_650_000, 5.70, 100.0, "Broker",
           "pursue", "Last-mile Phoenix at 5.70% cap clears mandate floor; PLG sponsor.",
           [], "pass",
           "Re-UW T-12 NOI. PLG overstated cap; true is closer to 5.15%. Don't trust their numbers.",
           340),
    _entry("hist-plg-02", "Cactus Crossroads Logistics", "Phoenix Logistics Group", "CBRE",
           "Phoenix", "AZ", "85027", "Industrial",
           280_000, 58_000_000, 3_390_000, 5.85, 100.0, "Broker",
           "pursue", "Second PLG deal; mandate-fit asset class and geography.",
           ["WALT 4.1 yrs"], "pass",
           "Same PLG pattern. Pulled their rent roll and effective cap is 5.20%. Pass.",
           220),
    _entry("hist-plg-03", "Sky Harbor Industrial Park", "Phoenix Logistics Group", None,
           "Phoenix", "AZ", "85034", "Industrial",
           410_000, 88_000_000, 5_100_000, 5.80, 98.0, "Owner",
           "pursue", "Larger PLG deal, off-market. Phoenix industrial in mandate.",
           ["Off-market: no comp validation"], "pass",
           "Third PLG strike. Cap consistently overstated 40-60bps. Adding to sponsor watchlist.",
           110),

    # Pattern 2: Cornerstone Equity Partners, IC-death streak
    _entry("hist-cep-01", "Lakeshore Apartments", "Cornerstone Equity Partners", "JLL",
           "Charlotte", "NC", "28269", "Multifamily",
           260_000, 72_000_000, 4_320_000, 6.00, 91.0, "Broker",
           "pursue", "Charlotte MF at 6.00% cap, sponsor has 3 prior MF exits.",
           ["Sponsor leverage profile aggressive"], "pass",
           "Killed at IC. CEP over-levered the cap stack, weak GP commit. First red flag.",
           210),
    _entry("hist-cep-02", "Whitestone Industrial", "Cornerstone Equity Partners", "JLL",
           "Atlanta", "GA", "30318", "Industrial",
           340_000, 68_000_000, 4_080_000, 6.00, 100.0, "Broker",
           "pursue", "Atlanta last-mile, CEP sponsor.", [], "pass",
           "Second CEP loss at IC. Bench is too thin for asset-management complexity.",
           160),
    _entry("hist-cep-03", "Bluestem Heights", "Cornerstone Equity Partners", "CBRE",
           "Nashville", "TN", "37013", "Multifamily",
           220_000, 56_000_000, 3_300_000, 5.89, 89.0, "Broker",
           "pursue", "Nashville growth MSA, mandate fit, sponsor known to firm.",
           ["Sponsor's prior asset under-performed UW"], "pass",
           "Third CEP IC death. Pattern is real; pass all CEP unless equity check >=$80M.",
           95),
    _entry("hist-cep-04", "Ironwood Logistics", "Cornerstone Equity Partners", "JLL",
           "Indianapolis", "IN", "46241", "Industrial",
           280_000, 88_000_000, 5_280_000, 6.00, 100.0, "Broker",
           "pursue", "Largest CEP deal yet, $88M, Indy last-mile.",
           ["Sponsor pattern: see watchlist"], "pursue",
           "Big enough check ($88M) for Linwood control rights. Pursued with structural protections.",
           50),

    # Pattern 3: Halcyon Residential, strong track record
    _entry("hist-hal-01", "Cypress Trails Phase I", "Halcyon Residential", "Newmark",
           "Austin", "TX", "78701", "Multifamily",
           300_000, 78_000_000, 4_290_000, 5.50, 93.0, "Broker",
           "pursue", "Halcyon's 4th Texas exit, mandate-perfect Sun Belt MF.",
           [], "pursue", "Exited 1.9x EM in 26 months. Halcyon delivers.", 380),
    _entry("hist-hal-02", "Sunridge Heights", "Halcyon Residential", "Newmark",
           "Phoenix", "AZ", "85016", "Multifamily",
           198_000, 54_000_000, 3_080_000, 5.70, 91.5, "Broker",
           "pursue", "Halcyon's first AZ deal. Mandate fit, sponsor proven.",
           ["Phoenix concession environment elevated"], "pursue", None, 280),

    # Standard variety
    _entry("hist-001", "Briar Creek Apartments", "Northwood Residential", "Newmark",
           "Charlotte", "NC", "28210", "Multifamily",
           240_000, 62_000_000, 3_700_000, 5.97, 93.0, "Broker",
           "pursue", "5.97% cap on Class B Charlotte; sponsor has 5 prior MF exits.",
           ["Roof capex ~$1.1M deferred"], "pursue", None, 400),
    _entry("hist-002", "Crossroads Logistics Center", "Stonewall Capital", "JLL",
           "Dallas", "TX", "75061", "Industrial",
           420_000, 78_000_000, 4_550_000, 5.83, 100.0, "Broker",
           "pursue", "Last-mile DFW, full lease, mandate fit.",
           ["WALT 4.2 yrs"], "pursue", None, 360),
    _entry("hist-003", "Toledo Logistics Park", "Midwest Industrial REIT", None,
           "Toledo", "OH", "43611", "Industrial",
           380_000, 34_000_000, 2_550_000, 7.50, 100.0, "Owner",
           "pass",
           "Tertiary-market industrial under $50M; outside hard rule.",
           ["Tertiary market", "No rail adjacency"], "pass",
           "Exactly the deal that produced the tertiary-industrial-<$50M rule.",
           320),
    _entry("hist-004", "Crystal Springs Tower", "Coastline Investments", "Newmark",
           "Miami", "FL", "33131", "Multifamily",
           320_000, 145_000_000, 6_100_000, 4.21, 95.0, "Broker",
           "pass", "Sub-5% cap; below mandate floor.",
           ["Cap rate below 5.0% floor"], "pass", None, 290),
    _entry("hist-005", "Crescent Tower", "Capital City Office REIT", "Vantage RE",
           "Charlotte", "NC", "28202", "Office",
           260_000, 78_000_000, 4_400_000, 5.64, 80.0, "Broker",
           "pass", "Office outside NYC/SF/BOS/DC mandate; hard pass.",
           [], "pass", None, 240),
    _entry("hist-006", "Big Sky Distribution", "Mountain States Logistics", "Vantage RE",
           "Billings", "MT", "59101", "Industrial",
           620_000, 88_000_000, 6_400_000, 7.27, 100.0, "Broker",
           "pass", "Out-of-mandate big-box (>500k sqft) and tertiary geo.",
           ["Big-box format", "Geography"], "pass", None, 130),
    _entry("hist-007", "Rivergate Distribution", "Heartland Industrial", "JLL",
           "Indianapolis", "IN", "46241", "Industrial",
           280_000, 56_000_000, 3_300_000, 5.89, 100.0, "Broker",
           "pursue", "Indy top-50 MSA, shallow-bay last-mile.",
           [], "pursue", None, 175),
    _entry("hist-008", "Northgate Plaza", "Tradeway Retail Partners", "CBRE",
           "Raleigh", "NC", "27604", "Retail",
           160_000, 38_000_000, 2_280_000, 6.00, 95.0, "Broker",
           "pursue", "Grocery-anchored (Publix), daily-needs co-tenants.",
           [], "pursue", None, 250),
    _entry("hist-009", "Maple Vista", "Atlanta Multifamily Partners", "Newmark",
           "Atlanta", "GA", "30309", "Multifamily",
           160_000, 42_000_000, 2_350_000, 5.60, 87.0, "Broker",
           "pursue", "Midtown Atlanta value-add story credible.",
           [], "pursue", None, 145),
    _entry("hist-010", "Pacific Heights Plaza", "West Coast Office Holdings", "CBRE",
           "San Francisco", "CA", "94104", "Office",
           310_000, 165_000_000, 7_200_000, 4.36, 72.0, "Broker",
           "pass", "Below 85% occupancy floor; SF lease-up risk too high.",
           ["Occupancy 72%"], "pursue",
           "Disagree; at this basis the lease-up risk is priced in. Push for diligence.",
           180),
]


# ---- sponsor + broker rows ----
#
# Counts come from HISTORICAL_DEALS so they stay consistent. Engagement
# summaries are hand-crafted seed values; at runtime the writer rewrites
# them per memo.


def _counts_for_sponsor(name: str) -> tuple[int, int, datetime]:
    matching = [d for d in HISTORICAL_DEALS if d.deal.sponsor == name]
    n_memos = len(matching)
    n_pursues = sum(1 for d in matching if d.analyst_action.decision == "pursue")
    last = max(d.created_at for d in matching) if matching else datetime.now(tz=timezone.utc)
    return n_memos, n_pursues, last


def _counts_for_broker(name: str) -> tuple[int, int, datetime]:
    matching = [d for d in HISTORICAL_DEALS if d.deal.broker == name]
    n_memos = len(matching)
    n_pursues = sum(1 for d in matching if d.analyst_action.decision == "pursue")
    last = max(d.created_at for d in matching) if matching else datetime.now(tz=timezone.utc)
    return n_memos, n_pursues, last


def _sponsor(name: str, summary: str) -> SponsorRecord:
    n_memos, n_pursues, last = _counts_for_sponsor(name)
    return SponsorRecord(
        name=name,
        n_memos=n_memos,
        n_pursues=n_pursues,
        engagement_summary=summary,
        last_updated=last,
    )


def _broker(name: str, summary: str) -> BrokerRecord:
    n_memos, n_pursues, last = _counts_for_broker(name)
    return BrokerRecord(
        name=name,
        n_memos=n_memos,
        n_pursues=n_pursues,
        engagement_summary=summary,
        last_updated=last,
    )


INITIAL_SPONSORS: list[SponsorRecord] = [
    _sponsor(
        "Phoenix Logistics Group",
        "3 prior deals (Desert Bay, Cactus Crossroads, Sky Harbor), all "
        "shallow-bay Phoenix industrial. All passed at IC: analyst re-"
        "underwriting consistently finds cap rates overstated by 40-60bps. "
        "Pattern is reliable; do not trust PLG-quoted cap rates. Apply a "
        "5.0% effective cap before accepting pricing.",
    ),
    _sponsor(
        "Cornerstone Equity Partners",
        "4 prior deals submitted 2025-Q2 through 2025-Q4. 3 died at IC "
        "(over-levered structures, weak GP commit, thin sponsor bench). "
        "The one pursued (Ironwood, $88M) cleared only because check size "
        "enabled Linwood control rights. Default to pass unless equity "
        "check is >=$80M with meaningful structural protections.",
    ),
    _sponsor(
        "Halcyon Residential",
        "2 prior deals (Cypress Trails Austin, Sunridge Heights Phoenix), "
        "both pursued. Cypress Trails exited at 1.9x equity multiple in "
        "26 months. Strong track record on Sun Belt multifamily; prefer "
        "their deals when underwriting is otherwise marginal.",
    ),
    # Singleton sponsors: one data point doesn't establish a pattern, so
    # keep these terse. Runtime updates will flesh them out.
    _sponsor(
        "Northwood Residential",
        "1 prior deal (Briar Creek Apartments Charlotte) pursued. "
        "5.97% cap on Class B; sponsor has 5 prior MF exits.",
    ),
    _sponsor(
        "Stonewall Capital",
        "1 prior deal (Crossroads Logistics DFW) pursued. Last-mile, full "
        "lease, mandate-fit industrial.",
    ),
    _sponsor(
        "Midwest Industrial REIT",
        "1 prior deal (Toledo Logistics Park) passed: tertiary-market "
        "industrial under $50M, the exact deal that produced the hard rule.",
    ),
    _sponsor(
        "Coastline Investments",
        "1 prior deal (Crystal Springs Tower Miami) passed: sub-5% cap, "
        "below mandate floor.",
    ),
    _sponsor(
        "Capital City Office REIT",
        "1 prior deal (Crescent Tower Charlotte) passed: office outside "
        "NYC/SF/BOS/DC mandate.",
    ),
    _sponsor(
        "Mountain States Logistics",
        "1 prior deal (Big Sky Distribution Billings) passed: out-of-"
        "mandate big-box (>500k sqft) and tertiary geography.",
    ),
    _sponsor(
        "Heartland Industrial",
        "1 prior deal (Rivergate Distribution Indy) pursued: top-50 MSA "
        "shallow-bay last-mile.",
    ),
    _sponsor(
        "Tradeway Retail Partners",
        "1 prior deal (Northgate Plaza Raleigh) pursued: grocery-anchored "
        "with daily-needs co-tenants.",
    ),
    _sponsor(
        "Atlanta Multifamily Partners",
        "1 prior deal (Maple Vista Atlanta) pursued: credible Midtown "
        "value-add story.",
    ),
    _sponsor(
        "West Coast Office Holdings",
        "1 prior deal (Pacific Heights Plaza SF): agent recommended pass "
        "for sub-85% occupancy; analyst overrode to pursue, arguing lease-"
        "up risk was priced into basis.",
    ),
]


INITIAL_BROKERS: list[BrokerRecord] = [
    _broker(
        "CBRE",
        "5 prior deals: 2 pursued (Northgate retail, Pacific Heights SF with "
        "analyst override at deep basis), 3 passed (2 PLG cap-overstatement "
        "deals, 1 CEP IC death). Mixed signal; CBRE-sourced deals are "
        "high-volume but require careful UW. Sponsor matters more than the "
        "broker relationship here.",
    ),
    _broker(
        "JLL",
        "5 prior deals: 3 pursued (Crossroads DFW industrial, Rivergate Indy, "
        "Ironwood CEP with control rights), 2 passed (CEP Whitestone, CEP "
        "Lakeshore, both IC deaths). Industrial pipeline is strong; "
        "multifamily flow is occasional and tends to come with weaker sponsors.",
    ),
    _broker(
        "Newmark",
        "5 prior deals: 4 pursued (3 MF in growth MSAs with clean exits, "
        "1 Atlanta value-add), 1 passed (Crystal Springs Miami at sub-5% cap). "
        "Reliable multifamily channel; prioritize Newmark MF forwards.",
    ),
    _broker(
        "Vantage RE",
        "2 prior deals: both passed. Crescent Tower was out-of-mandate "
        "Charlotte office; Big Sky was big-box tertiary industrial. Pattern: "
        "Vantage shops deals that don't fit Linwood's thesis. Skim quickly, "
        "default to pass unless primary-market with comp-validated pricing.",
    ),
]


__all__ = [
    "INITIAL_FIRM_DOC",
    "INITIAL_SPONSORS",
    "INITIAL_BROKERS",
    "HISTORICAL_DEALS",
]
