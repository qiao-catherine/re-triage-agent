"""Seed the platform's runtime Store via the HTTP API.

Usage (with `langgraph dev` running on :2024):

    python -m ac_deal_triage.seed_store

The custom-app lifespan runs before the platform attaches its store, so
seeding from inside a route writes to a phantom InMemoryStore. The graph
nodes write to the real platform store via `langgraph.config.get_store()`;
this script talks to the same store via the HTTP API.

All writes are unconditional upserts so schema changes propagate on rerun.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langgraph_sdk import get_client

from .schemas import FirmMemory
from .seed import (
    HISTORICAL_DEALS,
    INITIAL_BROKERS,
    INITIAL_FIRM_DOC,
    INITIAL_SPONSORS,
)

# parents[3] is the repo root: backend/src/ac_deal_triage/seed_store.py
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"
if _ROOT_ENV.exists():
    load_dotenv(_ROOT_ENV)

DEPLOYMENT_URL = os.getenv("DEPLOYMENT_URL", "http://localhost:2024")
API_KEY = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")

FIRM_NAMESPACE = ("firm",)
FIRM_KEY = "policies"
DEALS_NAMESPACE = ("deals",)
SPONSORS_NAMESPACE = ("sponsors",)
BROKERS_NAMESPACE = ("brokers",)


async def seed() -> None:
    client = get_client(url=DEPLOYMENT_URL, api_key=API_KEY)

    firm = FirmMemory(
        doc=INITIAL_FIRM_DOC,
        updated_at=datetime.now(tz=timezone.utc),
    )
    await client.store.put_item(
        FIRM_NAMESPACE, FIRM_KEY, firm.model_dump(mode="json")
    )
    print(f"  + upserted firm doc ({len(INITIAL_FIRM_DOC)} chars)")

    for sponsor in INITIAL_SPONSORS:
        await client.store.put_item(
            SPONSORS_NAMESPACE,
            sponsor.name,
            sponsor.model_dump(mode="json"),
        )
    print(f"  + upserted {len(INITIAL_SPONSORS)} sponsors")

    for broker in INITIAL_BROKERS:
        await client.store.put_item(
            BROKERS_NAMESPACE,
            broker.name,
            broker.model_dump(mode="json"),
        )
    print(f"  + upserted {len(INITIAL_BROKERS)} brokers")

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
