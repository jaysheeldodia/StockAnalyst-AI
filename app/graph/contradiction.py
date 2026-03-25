from __future__ import annotations

from collections import defaultdict

from app.models import Contradiction, Signal
from app.observability import traced
from app.state import GraphState


@traced("contradiction_checker_node")
async def contradiction_checker_node(state: GraphState) -> GraphState:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for signal in state["weighted_signals"]:
        grouped[(signal.get("topic") or "general").lower()].append(signal)

    contradictions: list[dict] = []
    for topic, signals in grouped.items():
        directions = {signal["direction"] for signal in signals if signal["direction"] != "neutral"}
        if len(directions) > 1:
            contradictions.append(
                Contradiction(
                    topic=topic,
                    conflicting_claims=[Signal(**signal) for signal in signals],
                ).model_dump()
            )

    plan = dict(state["plan"])
    if contradictions and state["iteration_count"] < 2:
        plan["follow_up_queries"] = [
            f"Resolve contradiction for topic '{item['topic']}' on {state['ticker']}"
            for item in contradictions
        ]
        return {
            "contradictions": contradictions,
            "plan": plan,
            "iteration_count": state["iteration_count"] + 1,
        }

    if contradictions:
        plan["follow_up_queries"] = []
        return {"contradictions": contradictions, "plan": plan}

    plan["follow_up_queries"] = []
    return {"contradictions": contradictions, "plan": plan}


def contradiction_router(state: GraphState) -> str:
    if state["contradictions"] and state["iteration_count"] < 2 and state["plan"].get("follow_up_queries"):
        return "planner"
    return "thesis_engine"
