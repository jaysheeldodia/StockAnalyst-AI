from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone

from app.models import Signal
from app.observability import traced
from app.state import GraphState


SOURCE_TYPE_MAP = {
    "news_agent": "news",
    "transcript_agent": "earnings_call",
    "financials_agent": "financial_filings",
    "sentiment_agent": "social_media",
    "macro_agent": "macro",
}


def _normalize_timestamp(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()


@traced("signal_normalization_node")
async def signal_normalization_node(state: GraphState) -> GraphState:
    deduped: OrderedDict[str, dict] = OrderedDict()
    current_iteration = state["iteration_count"]
    current_results = [result for result in state["raw_results"] if result.get("iteration") == current_iteration]
    for result in current_results:
        for payload in result["signals"]:
            key = payload["claim"].strip().lower()
            normalized_payload = dict(payload)
            normalized_payload["source_type"] = payload.get("source_type") or SOURCE_TYPE_MAP.get(
                payload.get("agent"), "news"
            )
            normalized_payload["timestamp"] = _normalize_timestamp(payload["timestamp"])
            normalized_payload["confidence"] = max(0.0, min(float(payload["confidence"]), 1.0))
            normalized = Signal(
                **normalized_payload,
            ).model_dump()
            current = deduped.get(key)
            if current is None or normalized["confidence"] > current["confidence"]:
                deduped[key] = normalized
    return {"signals": list(deduped.values())}
