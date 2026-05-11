"""One-shot script to seed the platform's runtime Store.

Usage (with `langgraph dev` running on :2024):

    python -m ac_deal_triage.seed_store

Why this exists: `langgraph_api`'s custom-app lifespan runs before the
platform attaches its store to the app, so seeding from inside a custom
route writes to a phantom InMemoryStore. The graph nodes write to the
real platform store via `langgraph.config.get_store()`. To get them in
sync, this script talks to the platform's HTTP store API from outside.

Idempotent: firm doc is only written if missing, historical deals are
always upserted (cheap, lets schema changes propagate to seeded rows).
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from langgraph_sdk import get_client

from .schemas import FirmMemory
from .seed import HISTORICAL_DEALS, INITIAL_FIRM_DOC

DEPLOYMENT_URL = os.getenv("DEPLOYMENT_URL", "http://localhost:2024")
API_KEY = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")

FIRM_NAMESPACE = ("firm",)
FIRM_KEY = "policies"
DEALS_NAMESPACE = ("deals",)


async def seed() -> None:
    client = get_client(url=DEPLOYMENT_URL, api_key=API_KEY)

    # ---- firm doc -------------------------------------------------------
    existing_firm = await client.store.get_item(FIRM_NAMESPACE, FIRM_KEY)
    if existing_firm is None or not existing_firm.get("value"):
        firm = FirmMemory(
            doc=INITIAL_FIRM_DOC,
            updated_at=datetime.now(tz=timezone.utc),
        )
        await client.store.put_item(
            FIRM_NAMESPACE, FIRM_KEY, firm.model_dump(mode="json")
        )
        print(f"  + seeded firm doc ({len(INITIAL_FIRM_DOC)} chars)")
    else:
        print("  · firm doc already present, skipping")

    # ---- historical deals ----------------------------------------------
    # Upsert all seed entries — cheap, and lets schema evolutions (new
    # @computed_fields like `final_decision`) propagate without manual
    # backfill on subsequent runs.
    for entry in HISTORICAL_DEALS:
        await client.store.put_item(
            DEALS_NAMESPACE,
            entry.memo_id,
            entry.model_dump(mode="json"),
        )
    print(f"  + upserted {len(HISTORICAL_DEALS)} historical deals")


def main() -> None:
    print(f"seeding store at {DEPLOYMENT_URL} ...")
    asyncio.run(seed())
    print("done.")


if __name__ == "__main__":
    main()
