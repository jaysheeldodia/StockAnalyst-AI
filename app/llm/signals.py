from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.llm.client import get_chat_model, is_llm_configured

logger = logging.getLogger(__name__)


class LlmSignalItem(BaseModel):
    claim: str = Field(description="A single, testable investment claim")
    evidence: str = Field(description="Why this holds, tied to context when possible")
    source: str = Field(description="Attribution, e.g. retrieved doc label or 'LLM synthesis'")
    confidence: float = Field(ge=0.0, le=1.0)
    direction: Literal["bullish", "bearish", "neutral"]
    topic: str = Field(description="Short topic label for grouping and contradiction checks")


class LlmSignalsBundle(BaseModel):
    signals: list[LlmSignalItem] = Field(
        min_length=2,
        max_length=6,
        description="Distinct, non-overlapping signals",
    )


ROLE_INSTRUCTIONS: dict[str, str] = {
    "news_agent": (
        "You focus on recent company news, media narratives, regulatory headlines, "
        "and catalysts that could move the stock."
    ),
    "transcript_agent": (
        "You focus on earnings-call style content: management tone, guidance, margins, "
        "demand commentary, and capital allocation."
    ),
    "financials_agent": (
        "You focus on financial statements: growth, profitability, cash flow, balance sheet, "
        "and valuation-relevant metrics."
    ),
    "sentiment_agent": (
        "You focus on retail/social sentiment, retail narratives, and positioning "
        "around the name (not verified trade data)."
    ),
    "macro_agent": (
        "You focus on macro drivers: rates, FX, sector cycles, and economic factors "
        "that affect this ticker."
    ),
}


def _format_context(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return (
            "(No documents were retrieved from the vector store. "
            "Produce cautious, lower-confidence signals and state limited visibility.)"
        )
    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata") or {}
        st = meta.get("source_type", "document")
        text = chunk.get("text") or ""
        parts.append(f"--- Chunk {i} [{st}] ---\n{text.strip()}")
    return "\n\n".join(parts)


def _follow_up_block(plan: dict, iteration_count: int) -> str:
    queries = plan.get("follow_up_queries") or []
    if not queries or iteration_count == 0:
        return ""
    return (
        "\n\nContradiction-resolution pass: prioritize these follow-up angles:\n"
        + "\n".join(f"- {q}" for q in queries)
    )


async def generate_signals_with_llm(
    *,
    agent_name: str,
    ticker: str,
    retrieval_objective: str,
    retrieved_context: list[dict[str, Any]],
    plan: dict,
    iteration_count: int,
) -> list[dict[str, Any]] | None:
    if not is_llm_configured():
        return None
    model = get_chat_model()
    if model is None:
        return None

    role = ROLE_INSTRUCTIONS.get(agent_name, "You are a sell-side style research analyst.")
    structured = model.with_structured_output(LlmSignalsBundle)
    ctx = _format_context(retrieved_context)
    follow = _follow_up_block(plan, iteration_count)

    prompt = f"""You are a senior equity research analyst. {role}

Ticker: {ticker}
Retrieval objective: {retrieval_objective}

Retrieved context (from internal RAG / vector store):
{ctx}
{follow}

Rules:
- Output 3–5 signals. Each must include a clear topic for cross-agent comparison.
- Ground claims in retrieved context when possible; if context is thin, say so and use lower confidence.
- direction must reflect how the signal would skew a long investor (bullish/bearish/neutral).
- source should name the chunk or say "Synthesis from retrieved context" / "Limited data — inferential".
- Be specific to {ticker}; avoid generic filler."""

    try:
        result: LlmSignalsBundle = await structured.ainvoke(prompt)
    except Exception:
        logger.exception("LLM signal generation failed for %s", agent_name)
        return None

    def _parse_context_ts(s: str | None) -> str | None:
        if not s:
            return None
        try:
            # Handle common ISO forms from web data (e.g. trailing Z).
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return None

    def _pick_fresh_ts(chunks: list[dict[str, Any]]) -> tuple[str, float]:
        """
        Returns (timestamp_iso_utc, freshness_confidence 0..1).

        freshness_confidence is higher when retrieved context provides a usable published_at.
        """
        published: list[str] = []
        for chunk in chunks:
            meta = chunk.get("metadata") or {}
            published_at = meta.get("published_at")
            ts = _parse_context_ts(str(published_at)) if published_at is not None else None
            if ts:
                published.append(ts)
        now = datetime.now(timezone.utc)
        if not published:
            return now.isoformat(), 0.45

        # Prefer the most recent available published timestamp.
        picked = max(published)
        try:
            age_days = (now - datetime.fromisoformat(picked.replace("Z", "+00:00"))).total_seconds() / 86400.0
        except Exception:
            age_days = 7.0

        # Simple step function: very fresh => high confidence; older => lower confidence.
        if age_days <= 2:
            fresh = 0.95
        elif age_days <= 14:
            fresh = 0.80
        else:
            fresh = 0.62
        return picked, fresh

    ctx_ts, freshness_conf = _pick_fresh_ts(retrieved_context)

    def _evidence_quality(evidence: str) -> float:
        ev = evidence or ""
        length_score = min(len(ev) / 260.0, 1.0)  # ~260 chars => full score
        digit_count = sum(1 for c in ev if c.isdigit())
        numeric_score = min(digit_count / 8.0, 1.0)
        # Weight: evidence clarity typically correlates with usefulness more than digits.
        return max(0.0, min(1.0, 0.70 * length_score + 0.30 * numeric_score))

    out: list[dict[str, Any]] = []
    for s in result.signals:
        out.append(
            {
                "claim": s.claim.strip(),
                "evidence": s.evidence.strip(),
                "source": s.source.strip(),
                "confidence": float(s.confidence),
                "timestamp": ctx_ts,
                "direction": s.direction,
                "topic": s.topic.strip(),
                "evidence_quality": _evidence_quality(s.evidence),
                "freshness_confidence": freshness_conf,
            }
        )
    return out if out else None


def weighted_signals_json(weighted: list[dict]) -> str:
    slim = []
    for w in weighted[:40]:
        slim.append(
            {
                "claim": w.get("claim"),
                "direction": w.get("direction"),
                "score": round(float(w.get("score", 0)), 4),
                "source_type": w.get("source_type"),
                "topic": w.get("topic"),
            }
        )
    return json.dumps(slim, indent=2)


def contradictions_json(contradictions: list) -> str:
    if not contradictions:
        return "[]"
    out = []
    for c in contradictions:
        if isinstance(c, dict):
            out.append({"topic": c.get("topic"), "n_claims": len(c.get("conflicting_claims", []))})
    return json.dumps(out, indent=2)
