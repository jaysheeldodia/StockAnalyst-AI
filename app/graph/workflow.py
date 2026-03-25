from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.agents import (
    financials_agent_node,
    macro_agent_node,
    news_agent_node,
    sentiment_agent_node,
    transcript_agent_node,
)
from app.graph.contradiction import contradiction_checker_node, contradiction_router
from app.graph.normalization import signal_normalization_node
from app.graph.orchestrator import orchestrator_node
from app.graph.market_snapshot import market_snapshot_node
from app.graph.planner import planner_node
from app.graph.report import report_writer_node
from app.graph.thesis import thesis_engine_node
from app.state import GraphState


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("market_snapshot", market_snapshot_node)
    graph.add_node("planner", planner_node)
    graph.add_node("news_agent", news_agent_node)
    graph.add_node("transcript_agent", transcript_agent_node)
    graph.add_node("financials_agent", financials_agent_node)
    graph.add_node("sentiment_agent", sentiment_agent_node)
    graph.add_node("macro_agent", macro_agent_node)
    graph.add_node("signal_normalization", signal_normalization_node)
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("contradiction_checker", contradiction_checker_node)
    graph.add_node("thesis_engine", thesis_engine_node)
    graph.add_node("report_writer", report_writer_node)

    graph.add_edge(START, "market_snapshot")
    graph.add_edge("market_snapshot", "planner")
    graph.add_edge("planner", "news_agent")
    graph.add_edge("planner", "transcript_agent")
    graph.add_edge("planner", "financials_agent")
    graph.add_edge("planner", "sentiment_agent")
    graph.add_edge("planner", "macro_agent")

    graph.add_edge("news_agent", "signal_normalization")
    graph.add_edge("transcript_agent", "signal_normalization")
    graph.add_edge("financials_agent", "signal_normalization")
    graph.add_edge("sentiment_agent", "signal_normalization")
    graph.add_edge("macro_agent", "signal_normalization")

    graph.add_edge("signal_normalization", "orchestrator")
    graph.add_edge("orchestrator", "contradiction_checker")
    graph.add_conditional_edges(
        "contradiction_checker",
        contradiction_router,
        {"planner": "planner", "thesis_engine": "thesis_engine"},
    )
    graph.add_edge("thesis_engine", "report_writer")
    graph.add_edge("report_writer", END)
    return graph.compile()
