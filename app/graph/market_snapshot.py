from __future__ import annotations

from app.audit.metadata import build_audit_metadata
from app.market.yfinance_snapshot import fetch_market_snapshot_async
from app.observability import traced
from app.state import GraphState


@traced("market_snapshot_node")
async def market_snapshot_node(state: GraphState) -> GraphState:
    horizon = state.get("horizon") or "12m"
    snapshot = await fetch_market_snapshot_async(state["ticker"])
    audit = build_audit_metadata(horizon, snapshot)
    return {"market_snapshot": snapshot, "audit": audit}
