from __future__ import annotations

import json

from app.audit.metadata import finalize_audit
from app.legal.disclaimer import RESEARCH_DISCLAIMER
from app.llm.synthesis import write_report_with_llm
from app.observability import traced
from app.state import GraphState
from app.storage.sqlite_store import SQLiteStore


def _citation(signal: dict) -> str:
    return (
        f"- [{signal['source_type']}] {signal['claim']} "
        f"(score={signal['score']:.2f}, source={signal['source']}, ts={signal['timestamp']})"
    )


def _template_report(state: GraphState, thesis: dict) -> str:
    top_evidence = "\n".join(_citation(signal) for signal in state["weighted_signals"][:8])
    return f"""# Executive Summary
{state['ticker']} screens with a confidence score of {thesis['confidence_score']:.2f}. The current setup reflects a weighted mix of company fundamentals, management commentary, market narrative, and macro context.

## Bull vs Bear Cases
### Bull Case
""" + "\n".join(f"- {item}" for item in thesis["bull_case"]) + """

### Bear Case
""" + "\n".join(f"- {item}" for item in thesis["bear_case"]) + """

## Key Drivers
""" + "\n".join(f"- {item}" for item in thesis["key_drivers"]) + """

## Risks
""" + "\n".join(f"- {item}" for item in thesis["risks"]) + """

## Catalysts
""" + "\n".join(f"- {item}" for item in thesis["catalysts"]) + """

## Supporting Evidence
""" + top_evidence + """

## Confidence Score
- Overall confidence: {:.2f}
""".format(thesis["confidence_score"])


def _format_market_snapshot_table(state: GraphState) -> str:
    ms = state.get("market_snapshot") or {}
    if ms.get("error"):
        return f"| Field | Value |\n| --- | --- |\n| Status | Error: {ms.get('error')} |\n"
    q = ms.get("quote") or {}
    m = ms.get("metrics") or {}
    p = ms.get("profile") or {}
    rows = [
        ("Data as-of (UTC)", ms.get("as_of_utc", "—")),
        ("Source", ms.get("source", "—")),
        ("Name", q.get("name", "—")),
        ("Sector", p.get("sector", "—")),
        ("Industry", p.get("industry", "—")),
        ("Last price", f"{q.get('price')} {q.get('currency', '')}".strip()),
        ("P/E (trailing/forward)", str(m.get("pe_trailing"))),
        ("Market cap", str(m.get("market_cap"))),
        ("YTD return %", f"{m.get('ytd_return_pct'):.2f}" if m.get("ytd_return_pct") is not None else "—"),
        ("Distance from 52w high %", f"{m.get('distance_from_52w_high_pct'):.2f}" if m.get("distance_from_52w_high_pct") is not None else "—"),
        ("Position in 52w range %", f"{m.get('position_in_52w_range_pct'):.2f}" if m.get("position_in_52w_range_pct") is not None else "—"),
    ]
    lines = ["| Field | Value |", "| --- | --- |"]
    for k, v in rows:
        lines.append(f"| {k} | {v} |")
    return "\n".join(lines)


def build_report_appendix(state: GraphState) -> str:
    audit = finalize_audit(state.get("audit") or {})
    horizon = state.get("horizon", "12m")
    peer = (state.get("market_snapshot") or {}).get("peer_context", "")
    thesis = state.get("final_thesis") or {}
    fair_low = thesis.get("fair_value_low")
    fair_base = thesis.get("fair_value_base")
    fair_high = thesis.get("fair_value_high")
    imp_low = thesis.get("implied_return_low_pct")
    imp_base = thesis.get("implied_return_base_pct")
    imp_high = thesis.get("implied_return_high_pct")
    assumptions = thesis.get("valuation_assumptions") or None
    audit_json = json.dumps(audit, indent=2, default=str)
    parts = [
        "## Market snapshot (third-party data)",
        f"**Investment horizon (user-selected):** `{horizon}`",
        "",
        _format_market_snapshot_table(state),
        "",
        "**Sector / peer context**",
        peer or "—",
        "",
        "## Valuation Range (deterministic MVP)",
        "This range is computed from current market multiples and lightweight fundamental proxies (best-effort; may be incomplete).",
        "",
    ]

    if fair_low is None or fair_base is None or fair_high is None:
        parts.extend(
            [
                "- Fair value range: `—` (insufficient valuation inputs from yfinance).",
                "",
            ]
        )
    else:
        parts.extend(
            [
                f"- Fair value (bear / base / bull): **{fair_low:.2f}** / **{fair_base:.2f}** / **{fair_high:.2f}**",
                f"- Implied return % (bear / base / bull): **{imp_low:.1f}%** / **{imp_base:.1f}%** / **{imp_high:.1f}%**",
                "",
            ]
        )

    if assumptions:
        parts.extend(
            [
                "**Valuation assumptions snapshot**",
                "```json",
                json.dumps(assumptions, indent=2, default=str),
                "```",
                "",
            ]
        )

    parts.extend(
        [
            "## Data & audit",
            "```json",
            audit_json,
            "```",
            "",
            RESEARCH_DISCLAIMER,
        ]
    )

    return "\n".join(parts)


@traced("report_writer_node")
async def report_writer_node(state: GraphState) -> GraphState:
    thesis = state["final_thesis"]
    llm_report = await write_report_with_llm(
        state["ticker"],
        thesis,
        state["weighted_signals"],
        horizon=state.get("horizon", "12m"),
        market_snapshot=state.get("market_snapshot") or {},
    )
    if llm_report:
        report = llm_report
    else:
        report = _template_report(state, thesis)

    report = report.rstrip() + "\n\n" + build_report_appendix(state)

    await SQLiteStore().save_report(state["ticker"], report, thesis)
    return {"report": report}
