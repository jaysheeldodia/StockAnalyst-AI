from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    horizon: str = Field(default="12m", description="e.g. 1m, 3m, 6m, 12m, 24m")


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
