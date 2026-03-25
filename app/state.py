from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class GraphState(TypedDict):
    ticker: str
    horizon: str
    plan: dict
    market_snapshot: dict
    audit: dict
    raw_results: Annotated[list, operator.add]
    signals: list
    weighted_signals: list
    contradictions: list
    final_thesis: dict
    report: str
    iteration_count: int


def initial_state(ticker: str, horizon: str = "12m") -> GraphState:
    return {
        "ticker": ticker.upper().strip(),
        "horizon": horizon,
        "plan": {},
        "market_snapshot": {},
        "audit": {},
        "raw_results": [],
        "signals": [],
        "weighted_signals": [],
        "contradictions": [],
        "final_thesis": {},
        "report": "",
        "iteration_count": 0,
    }
