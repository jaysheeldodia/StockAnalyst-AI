from __future__ import annotations

from app.llm.synthesis import (
    compute_deterministic_valuation_range,
    synthesize_thesis_with_llm,
    thesis_from_signals_deterministic,
)
from app.models import Thesis
from app.observability import traced
from app.state import GraphState


@traced("thesis_engine_node")
async def thesis_engine_node(state: GraphState) -> GraphState:
    weighted = state["weighted_signals"]
    plan = dict(state["plan"])
    plan["follow_up_queries"] = []

    llm_thesis = await synthesize_thesis_with_llm(
        state["ticker"],
        weighted,
        state.get("contradictions") or [],
        horizon=state.get("horizon", "12m"),
        market_snapshot=state.get("market_snapshot") or {},
    )
    if llm_thesis:
        thesis: Thesis = llm_thesis
    else:
        thesis = thesis_from_signals_deterministic(weighted)

    valuation = compute_deterministic_valuation_range(
        state.get("market_snapshot") or {},
        state.get("horizon", "12m"),
    )
    if valuation:
        thesis = thesis.model_copy(update=valuation)

    return {"final_thesis": thesis.model_dump(), "plan": plan}
