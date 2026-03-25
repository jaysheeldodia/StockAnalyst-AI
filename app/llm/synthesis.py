from __future__ import annotations

import logging
from statistics import mean

from pydantic import BaseModel, Field

from app.llm.client import get_chat_model, is_llm_configured
from app.llm.signals import contradictions_json, weighted_signals_json
from app.models import Thesis

logger = logging.getLogger(__name__)


def _market_prompt_block(market_snapshot: dict | None, horizon: str) -> str:
    ms = market_snapshot or {}
    if ms.get("error"):
        return f"Market data error: {ms.get('error')}. Horizon: {horizon}."
    q = ms.get("quote") or {}
    m = ms.get("metrics") or {}
    p = ms.get("profile") or {}
    return (
        f"Investment horizon for this memo: **{horizon}**.\n"
        f"Market data as-of (UTC): **{ms.get('as_of_utc')}** (source: {ms.get('source')}).\n"
        f"Name: {q.get('name', '—')} | Sector: {p.get('sector')} | Industry: {p.get('industry')}\n"
        f"Last price: {q.get('price')} {q.get('currency', '')} | "
        f"P/E (trailing): {m.get('pe_trailing')} | "
        f"P/E (forward): {m.get('pe_forward')} | "
        f"Market cap: {m.get('market_cap')}\n"
        f"YTD return %: {m.get('ytd_return_pct')} | "
        f"Distance from 52w high %: {m.get('distance_from_52w_high_pct')} | "
        f"Position in 52w range % (0=low, 100=high): {m.get('position_in_52w_range_pct')}\n"
        f"Peer context: {ms.get('peer_context', '')}"
    )


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def compute_deterministic_valuation_range(
    market_snapshot: dict | None,
    horizon: str,
) -> dict[str, float | dict[str, float | str | None] | None]:
    """
    Lightweight deterministic valuation range.

    This is intentionally simple/inspectable (MVP) and uses whatever yfinance fields
    are available. If required fields are missing, it returns mostly None.
    """

    ms = market_snapshot or {}
    if ms.get("error"):
        return {}

    q = ms.get("quote") or {}
    m = ms.get("metrics") or {}
    price = m.get("price") or q.get("price")
    if price is None:
        return {}

    trailing_pe = m.get("pe_trailing")
    forward_pe = m.get("pe_forward")
    base_pe = forward_pe if forward_pe is not None else trailing_pe
    if base_pe is None or base_pe == 0:
        return {}

    # Fundamentals for "quality" shaping.
    profit_margins = m.get("profit_margins")
    operating_margins = m.get("operating_margins")
    revenue_growth = m.get("revenue_growth")
    earnings_growth = m.get("earnings_growth")
    free_cashflow = m.get("free_cashflow")
    market_cap = m.get("market_cap")
    debt_to_equity = m.get("debt_to_equity")

    # Choose a single growth estimate.
    growth_est = earnings_growth if earnings_growth is not None else revenue_growth
    if growth_est is None:
        growth_est = 0.07

    margin_est = operating_margins if operating_margins is not None else profit_margins
    if margin_est is None:
        margin_est = 0.20

    # Convert to normalized 0..1 scores.
    growth_score = _clamp((growth_est + 0.05) / 0.30, 0.0, 1.0)  # -0.05..0.25 maps to 0..1
    margin_score = _clamp(margin_est / 0.30, 0.0, 1.0)  # 0..0.30 -> 0..1
    if free_cashflow is not None and market_cap not in (None, 0):
        fcf_yield = float(free_cashflow) / float(market_cap)
        fcf_yield_score = _clamp(fcf_yield / 0.08, 0.0, 1.0)  # 0..8% -> 0..1
    else:
        fcf_yield_score = 0.5

    if debt_to_equity is None:
        leverage_bad_score = 0.5
    else:
        leverage_bad_score = _clamp(float(debt_to_equity) / 2.0, 0.0, 1.0)  # >2 = quite levered

    # Overall "quality" 0..1 (higher is better).
    quality = 0.40 * growth_score + 0.35 * margin_score + 0.15 * fcf_yield_score + 0.10 * (1.0 - leverage_bad_score)

    # Earnings estimate proxy from current P/E.
    eps_mult = trailing_pe if trailing_pe is not None else base_pe
    if eps_mult is None or eps_mult == 0:
        return {}
    eps_est = float(price) / float(eps_mult)

    # Base/bull/bear expected P/E bands, shaped by quality and growth.
    expected_pe = float(base_pe) * (1.0 + 0.08 * (quality - 0.5))
    bull_pe = expected_pe * (1.0 + 0.12 + 0.10 * growth_score)
    bear_pe = expected_pe * (1.0 - (0.12 + 0.10 * (1.0 - growth_score)))

    # Guardrails.
    expected_pe = max(expected_pe, 0.1)
    bull_pe = max(bull_pe, expected_pe)
    bear_pe = max(min(bear_pe, expected_pe), 0.05)

    fair_value_base = eps_est * expected_pe
    fair_value_low = eps_est * bear_pe
    fair_value_high = eps_est * bull_pe

    implied_return_low_pct = (fair_value_low / price - 1.0) * 100.0
    implied_return_base_pct = (fair_value_base / price - 1.0) * 100.0
    implied_return_high_pct = (fair_value_high / price - 1.0) * 100.0

    assumptions: dict[str, float | str | None] = {
        "horizon": horizon,
        "growth_est": float(growth_est),
        "margin_est": float(margin_est),
        "fcf_yield": float(free_cashflow) / float(market_cap) if free_cashflow is not None and market_cap not in (None, 0) else None,
        "quality_score": quality,
        "base_pe_used": float(base_pe),
        "expected_pe": expected_pe,
        "bull_pe": bull_pe,
        "bear_pe": bear_pe,
    }

    return {
        "fair_value_low": float(fair_value_low),
        "fair_value_base": float(fair_value_base),
        "fair_value_high": float(fair_value_high),
        "implied_return_low_pct": float(implied_return_low_pct),
        "implied_return_base_pct": float(implied_return_base_pct),
        "implied_return_high_pct": float(implied_return_high_pct),
        "valuation_assumptions": assumptions,
    }


class ThesisLLM(BaseModel):
    bull_case: list[str] = Field(default_factory=list, max_length=10)
    bear_case: list[str] = Field(default_factory=list, max_length=10)
    key_drivers: list[str] = Field(default_factory=list, max_length=10)
    risks: list[str] = Field(default_factory=list, max_length=10)
    catalysts: list[str] = Field(default_factory=list, max_length=10)
    confidence_score: float = Field(ge=0.0, le=1.0)


async def synthesize_thesis_with_llm(
    ticker: str,
    weighted_signals: list[dict],
    contradictions: list,
    horizon: str = "12m",
    market_snapshot: dict | None = None,
) -> Thesis | None:
    if not is_llm_configured() or not weighted_signals:
        return None
    model = get_chat_model()
    if model is None:
        return None

    structured = model.with_structured_output(ThesisLLM)
    prompt = f"""You synthesize a professional equity thesis for ticker {ticker}.

Market & horizon context (ground your tone and risks in this when relevant):
{_market_prompt_block(market_snapshot, horizon)}

Weighted research signals (higher score = more important):
{weighted_signals_json(weighted_signals)}

Detected contradiction groups (if any):
{contradictions_json(contradictions)}

Requirements:
- bull_case and bear_case must be specific to {ticker}, not generic market commentary.
- key_drivers: 3–5 bullets tying together the strongest themes.
- risks: include both company-specific and macro where relevant.
- catalysts: near-term and medium-term events or metrics to watch.
- confidence_score: your holistic 0–1 confidence given signal quality and contradictions."""

    try:
        raw: ThesisLLM = await structured.ainvoke(prompt)
    except Exception:
        logger.exception("LLM thesis synthesis failed")
        return None

    return Thesis(
        bull_case=raw.bull_case,
        bear_case=raw.bear_case,
        key_drivers=raw.key_drivers,
        risks=raw.risks,
        catalysts=raw.catalysts,
        confidence_score=min(raw.confidence_score, 1.0),
    )


def thesis_from_signals_deterministic(weighted_signals: list[dict]) -> Thesis:
    def _collect(direction: str) -> list[str]:
        return [
            s["claim"]
            for s in weighted_signals
            if s.get("direction") == direction
        ][:5]

    bull = _collect("bullish")
    bear = _collect("bearish")
    weighted = weighted_signals
    return Thesis(
        bull_case=bull,
        bear_case=bear,
        key_drivers=[s["claim"] for s in weighted[:5]],
        risks=bear[:5] or ["Execution and macro risks remain mixed."],
        catalysts=[s["claim"] for s in weighted if s.get("direction") != "bearish"][:5],
        confidence_score=min(
            mean([float(s["score"]) for s in weighted]) if weighted else 0.0,
            1.0,
        ),
    )


async def write_report_with_llm(
    ticker: str,
    thesis: dict,
    weighted_signals: list[dict],
    horizon: str = "12m",
    market_snapshot: dict | None = None,
) -> str | None:
    if not is_llm_configured():
        return None
    model = get_chat_model()
    if model is None:
        return None

    evidence_lines = []
    for s in weighted_signals[:10]:
        evidence_lines.append(
            f"- [{s.get('source_type')}] {s.get('claim')} "
            f"(score={float(s.get('score', 0)):.2f}, src={s.get('source')})"
        )
    evidence_block = "\n".join(evidence_lines)

    prompt = f"""Write an institutional-style equity research memo in Markdown for ticker {ticker}.

Market & horizon (cite these figures where appropriate; they are from a live market data pull):
{_market_prompt_block(market_snapshot, horizon)}

Thesis JSON:
{thesis}

Top weighted evidence rows:
{evidence_block}

Required sections and headings (use exactly these H2 headings):
## Executive Summary
## Bull vs Bear Cases
### Bull Case
### Bear Case
## Key Drivers
## Risks
## Catalysts
## Supporting Evidence
## Confidence Score

Rules:
- Executive summary: 3–5 tight sentences referencing the thesis.
- Be specific to {ticker}; avoid filler.
- Supporting Evidence: bullet list citing source_type and claim.
- Confidence Score: state the numeric score from the thesis and interpret it briefly."""

    try:
        msg = await model.ainvoke(prompt)
    except Exception:
        logger.exception("LLM report generation failed")
        return None

    text = getattr(msg, "content", None)
    if isinstance(text, list):
        text = "".join(str(part) for part in text)
    if not text or not str(text).strip():
        return None
    return str(text).strip()
