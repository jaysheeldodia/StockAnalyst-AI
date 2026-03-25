from __future__ import annotations

import math
from datetime import datetime, timezone

from app.config import get_config
from app.observability import traced
from app.state import GraphState


def _days_old(timestamp: str) -> float:
    ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - ts.astimezone(timezone.utc)
    return max(delta.total_seconds() / 86400.0, 0.0)


@traced("orchestrator_node")
async def orchestrator_node(state: GraphState) -> GraphState:
    config = get_config()
    weighted = []
    for signal in state["signals"]:
        source_weight = config.weights.source_weights.get(signal["source_type"], 0.5)
        recency_weight = math.exp(-config.weights.recency_lambda * _days_old(signal["timestamp"]))

        evidence_quality = signal.get("evidence_quality")
        if evidence_quality is None:
            ev = signal.get("evidence") or ""
            length_score = min(len(ev) / 260.0, 1.0)
            digit_count = sum(1 for c in str(ev) if c.isdigit())
            numeric_score = min(digit_count / 8.0, 1.0)
            evidence_quality = max(0.0, min(1.0, 0.70 * length_score + 0.30 * numeric_score))

        freshness_confidence = signal.get("freshness_confidence")
        if freshness_confidence is None:
            # Default to medium confidence when context had no usable timestamps.
            freshness_confidence = 0.55

        eq_factor = 0.5 + 0.5 * float(evidence_quality)
        fc_factor = 0.5 + 0.5 * float(freshness_confidence)

        final_score = (
            signal["confidence"]
            * source_weight
            * recency_weight
            * (eq_factor ** config.weights.evidence_quality_weight)
            * (fc_factor ** config.weights.freshness_confidence_weight)
        )
        weighted.append(
            {
                **signal,
                "source_weight": source_weight,
                "recency_weight": recency_weight,
                "evidence_quality": evidence_quality,
                "freshness_confidence": freshness_confidence,
                "score": final_score,
            }
        )
    weighted.sort(key=lambda item: item["score"], reverse=True)
    return {"weighted_signals": weighted}
