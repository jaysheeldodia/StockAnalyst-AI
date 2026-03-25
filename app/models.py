from __future__ import annotations

from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, Field


SignalDirection = Literal["bullish", "bearish", "neutral"]


class Signal(BaseModel):
    claim: str
    evidence: str
    source: str
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: str
    direction: SignalDirection
    source_type: str | None = None
    topic: str | None = None
    score: float | None = None
    agent: str | None = None
    # MVP trust signals for better weighting/transparency.
    evidence_quality: float | None = None
    freshness_confidence: float | None = None


class Contradiction(BaseModel):
    topic: str
    conflicting_claims: list[Signal]


class Thesis(BaseModel):
    bull_case: list[str]
    bear_case: list[str]
    key_drivers: list[str]
    risks: list[str]
    catalysts: list[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    # Deterministic valuation range (set by thesis engine; optional for MVP).
    fair_value_low: float | None = None
    fair_value_base: float | None = None
    fair_value_high: float | None = None
    implied_return_low_pct: float | None = None
    implied_return_base_pct: float | None = None
    implied_return_high_pct: float | None = None
    valuation_assumptions: dict[str, float | str | None] | None = None


class ReportRecord(BaseModel):
    ticker: str
    report: str
    thesis: dict
    generated_at: datetime


class EvaluationRecord(BaseModel):
    ticker: str
    faithfulness: float | None = None
    answer_relevance: float | None = None
    context_precision: float | None = None
    notes: str | None = None


class GraphState(TypedDict):
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
