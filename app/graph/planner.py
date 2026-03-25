from __future__ import annotations

from datetime import datetime, timezone

from app.observability import traced
from app.state import GraphState


@traced("planner_node")
async def planner_node(state: GraphState) -> GraphState:
    follow_ups = state["plan"].get("follow_up_queries", [])
    ms = state.get("market_snapshot") or {}
    prof = ms.get("profile") or {}
    plan = {
        "objective": f"Produce an analyst-style report for {state['ticker']}",
        "horizon": state.get("horizon", "12m"),
        "research_tracks": [
            "news",
            "transcript",
            "financials",
            "sentiment",
            "macro",
        ],
        "follow_up_queries": follow_ups,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sector": prof.get("sector"),
        "industry": prof.get("industry"),
        "peer_context": ms.get("peer_context", ""),
    }
    return {"plan": plan}
