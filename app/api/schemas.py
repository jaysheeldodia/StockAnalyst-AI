from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    horizon: str = Field(default="12m", description="e.g. 1m, 3m, 6m, 12m, 24m")


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    score: float | None = Field(
        default=None, description="Retriever distance (lower is closer); live docs use -1.0"
    )
    source_url: str | None = None


class AnalyzeResponse(BaseModel):
    ticker: str
    horizon: str
    plan: dict
    market_snapshot: dict
    audit: dict
    raw_results: list
    signals: list
    weighted_signals: list
    contradictions: list
    final_thesis: dict
    report: str
    iteration_count: int
    retrieval: list[RetrievedChunk] = Field(default_factory=list)


def retrieval_from_raw_results(raw_results: list) -> list[RetrievedChunk]:
    """Flatten and de-duplicate the chunks every agent retrieved during a run."""
    seen: set[str] = set()
    chunks: list[RetrievedChunk] = []
    for result in raw_results or []:
        for item in result.get("retrieved_context") or []:
            text = item.get("text") or ""
            chunk_id = str(item.get("id") or hashlib.sha1(text.encode("utf-8")).hexdigest()[:12])
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            meta = item.get("metadata") or {}
            distance = item.get("distance")
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    text=text,
                    score=float(distance) if distance is not None else None,
                    source_url=meta.get("url") or meta.get("source_url"),
                )
            )
    return chunks
