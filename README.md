# Real Estate Deal Triage Agent

A real-estate-fund deal-triage demo built for the Applied Compute GTM
take-home. Inbound memo → triage agent (3 tools) → human review →
memory writer that closes the loop on every analyst click.

The wedge: every reviewer decision becomes durable signal in the firm's
policy doc and a labeled training row in LangSmith. The model gets sharper
over time because the data layer grows, not because we retrain.

## Repo layout

```
applied-compute/
├── backend/                       LangGraph deployment (Python)
│   ├── src/ac_deal_triage/
│   │   ├── graph.py               compiled graph (entry point)
│   │   ├── models.py              chat_model: one env var swaps providers
│   │   ├── schemas.py             DealContext, Recommendation, AnalystAction…
│   │   ├── tools.py               extract_fields, read_firm_memory, find_similar_deals
│   │   ├── prompts.py             triage agent system prompt
│   │   ├── store.py               read/write helpers for the platform Store
│   │   ├── seed.py                INITIAL_FIRM_DOC + 20 historical deals
│   │   ├── seed_store.py          one-shot script: writes seed → platform store
│   │   └── nodes/
│   │       ├── human_review.py    interrupt() with the HumanInterrupt payload
│   │       └── memory.py          deal entry + LangSmith feedback + firm-doc append
│   ├── langgraph.json
│   ├── pyproject.toml
│   └── pyrightconfig.json
│
├── frontend/                      Forked from langchain-ai/agent-inbox (Next.js)
│   ├── src/
│   │   ├── app/                   /, /done, /memory (3 tabs)
│   │   ├── components/
│   │   │   ├── agent-inbox/       inbox view + thread view (forked / customized)
│   │   │   ├── app-sidebar/
│   │   │   ├── inbox-bootstrap.tsx  auto-seeds deployment URL + API key from env
│   │   │   └── ui/                trimmed shadcn primitives we actually use
│   │   └── lib/
│   │       ├── client.ts          langgraph-sdk client factory
│   │       ├── deployment-api.ts  platform Store reads (memory + deals)
│   │       └── use-focus-refresh.ts
│   ├── next.config.mjs            loads ../.env at build time
│   └── package.json
│
├── .env.example                   single source of truth for both processes
├── .gitignore
└── README.md
```

## Topology

```
START → triage → human_review → memory_writer → END
```

- **triage**: ReAct agent with 3 tools and a structured `Recommendation` output
- **human_review**: Pauses the graph via `interrupt(...)` until the analyst clicks Submit
- **memory_writer**: Persists the `DealMemoryEntry`, writes 2 feedback rows to LangSmith, and (if the analyst's note generalizes) appends a paragraph to the firm policy doc

## Setup (one-time)

### 1. Env file

You will need a LangSmith API key and OpenAI key to run the demo. 
If you don't have one, you can create one at smith.langchain.com and openai.com. 

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY and LANGSMITH_API_KEY.
# DEPLOYMENT_URL defaults to http://localhost:2024 for local dev; replace with langgraph deployment URL for deployed agents
```

### 2. Python venv + backend deps

```bash
python3 -m venv .venv
source .venv/bin/activate
cd backend && pip install -e ".[dev]"
```

### 3. Frontend deps

```bash
cd frontend
yarn install
cd ..
```

## Run

### Terminal 1: backend

```bash
source .venv/bin/activate
cd backend
langgraph dev          # serves on http://localhost:2024
```

### One time, demo-purpose: populate initial memory

Within backend, run:

```bash
python -m ac_deal_triage.seed_store
```

Writes the initial firm-policy doc + 20 historical deals into the platform's
Store via the LangGraph SDK.

### Terminal 2: frontend

```bash
cd frontend
yarn dev               # serves on http://localhost:3000
```

Open `http://localhost:3000`.

## To run the agent

Three tabs in the sidebar:


| Tab             | What it shows                                         | Backed by                                                              |
| --------------- | ----------------------------------------------------- | ---------------------------------------------------------------------- |
| **For review**  | Pending memos for human review                        | LangGraph `POST /threads/search`                                       |
| **Done**        | Human reviewed deals with All / Pursue / Pass filter  | Platform Store `POST /store/items/search` filtered on `final_decision` |
| **Firm memory** | The growing policy markdown                           | Platform Store `POST /store/items/get` for `("firm","policies")`       |


To trigger a triage, open LangGraph Studio at
`https://smith.langchain.com/studio/?baseUrl=http://localhost:2024` (or
your deployed URL) or hit the
[/threads/runs](https://docs.langchain.com/langsmith/agent-server-api/thread-runs/list-runs)
endpoint directly. Send an input like:

```json
{
  "memo_id": "memo-001",
  "messages": [
    {"role": "user", "content": "From: kevin.osman@cbre.com\nTo: deals@linwood.capital\nSubject: New PLG industrial — Sonoran Bay Logistics, Phoenix AZ\n\nKevin here. Bringing you the latest from Phoenix Logistics Group:\n\n- 295,000 sqft shallow-bay industrial, two buildings, Goodyear AZ (Phoenix MSA)\n- 100% leased, blended WALT 4.8 yrs\n- Asking $62M, T-12 NOI ~$3.55M → 5.73% cap\n- PLG will deliver with $1.8M roof capex already escrowed\n\nLet me know if you want the full UW model."}
  ]
}
```

This memo is the killer demo case — Phoenix Logistics Group is on the
sponsor watchlist for cap-rate overstatement, and `find_similar_deals`
will surface all three prior PLG deals (which all got passed for the
same reason). Watch the agent cite the watchlist rule by name and flag
the pattern in `key_risks`.

The graph runs to the `human_review` interrupt, then surfaces in the
**For review** tab. Click into it, pick **Pursue** or **Pass**,
optionally add a note, click **Submit**. The thread completes and the
entry shows up in **Done**. If the note generalizes into a firm policy,
**Firm memory** picks up a new paragraph on next refresh.

### Other example memos worth trying

- **Halcyon Residential MF in Texas** — agent should weight the strong
  track record from `find_similar_deals` and pursue
- **Cornerstone Equity Partners deal under $80M** — agent should pass
  per the watchlist (3 prior IC deaths)
- **Tertiary industrial under $50M in Toledo / Wichita / etc.** — agent
  should pass per the explicit hard rule

In LangSmith, you can inspect that two feedback scores have been added onto the traces, recording the final analyst decision, as well as the computed reward (0 if agent decision does not align with human judgement, 1 otherwise)

## (Optional) Deployment

### Backend (LangSmith Deployments)

```bash
cd backend
langgraph deploy --name ac-deal-triage
```

Adopts the platform's managed Postgres for both the checkpointer and the
long-term Store. Update `.env` with the deployed URL, then seed:

```bash
# In .env:
#   DEPLOYMENT_URL=https://<your-deployment>.langgraph.app

cd backend
python -m ac_deal_triage.seed_store
```

The seed script auto-loads `.env`, so no inline env vars needed.

### Frontend (Vercel)

Should only be deployed after adding auth

```bash
cd frontend
vercel deploy --prod
```

Set these in Vercel's env vars (Project Settings → Environment Variables):


| Var                      | Value                       | Why server-only                              |
| ------------------------ | --------------------------- | -------------------------------------------- |
| `DEPLOYMENT_URL`         | Your deployed LangGraph URL | The proxy uses it; the browser never sees it |
| `LANGSMITH_API_KEY`      | Your LangSmith key          | Injected by the proxy into upstream calls    |
| `NEXT_PUBLIC_GRAPH_ID`   | `deal_triage`               | Safe to ship in the bundle                   |
| `NEXT_PUBLIC_INBOX_NAME` | `Deal Triage`               | Same                                         |


The `NEXT_PUBLIC_*` prefix is the only way Next.js inlines an env var into
the client bundle. Keep `LANGSMITH_API_KEY` and `DEPLOYMENT_URL` without
that prefix and they stay server-only.

## To be further added in production: 

See separate writeup for the full information: 
- The firm policy doc and 20 historical deals are seeded fixtures
- No authentication 
- No real email hook: memos arrive via Studio input (production: Gmail/SendGrid webhook → `/threads/runs`)
- No OM/PDF parsing: memos are plain text (production: tools like Reducto added before `extract_fields`)
- Using OpenAI `gpt-4.1-mini` instead of custom model
