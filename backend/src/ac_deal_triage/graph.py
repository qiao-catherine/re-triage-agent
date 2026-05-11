"""Compiled graph — exported as `graph` for LangGraph Platform to pick up.

Topology (linear):

    START → triage → human_review → memory_writer → END

The `triage` node is a `create_agent` call used **directly** as a node — no
wrapper. The agent reads `state["messages"]` (initial HumanMessage = the
memo), calls its three tools, and writes `state["structured_response"]`
(a Recommendation with both evidence and conclusion).

The HITL pause happens inside `human_review_node` via `interrupt(...)`; resume
arrives from agent-inbox through LangGraph's standard /runs/.../resume API.

Compiled without checkpointer/store — LangGraph Platform (and `langgraph dev`
locally) provide them at runtime.
"""

from __future__ import annotations

# `langgraph_api` loads this file via spec.loader.exec_module (not as a
# package member), so relative imports won't work — use absolute imports.
# The `ac_deal_triage` package is on sys.path because langgraph.json's
# `"dependencies": ["."]` triggers `pip install -e .` at boot.
from langchain.agents import create_agent
from langgraph.graph import END, START, StateGraph

from ac_deal_triage.models import chat_model
from ac_deal_triage.nodes.human_review import human_review_node
from ac_deal_triage.nodes.memory import memory_writer_node
from ac_deal_triage.prompts import TRIAGE_PROMPT
from ac_deal_triage.schemas import Recommendation, TriageState
from ac_deal_triage.tools import RESEARCH_TOOLS

# The single triage agent — gathers evidence via tools, emits Recommendation.
# `state_schema=TriageState` aligns the agent's I/O with our state, so it
# can be added as a node directly with no wrapper function.
triage_agent = create_agent(
    model=chat_model,
    tools=RESEARCH_TOOLS,
    system_prompt=TRIAGE_PROMPT,
    response_format=Recommendation,
    state_schema=TriageState,
    name="triage",
)

graph_builder = StateGraph(TriageState)
graph_builder.add_node("triage", triage_agent)
graph_builder.add_node("human_review", human_review_node)
graph_builder.add_node("memory_writer", memory_writer_node)

graph_builder.add_edge(START, "triage")
graph_builder.add_edge("triage", "human_review")
graph_builder.add_edge("human_review", "memory_writer")
graph_builder.add_edge("memory_writer", END)

graph = graph_builder.compile()
