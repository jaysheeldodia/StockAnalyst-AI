from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.config import get_config

logger = logging.getLogger(__name__)


def _stable_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"\x1f")
    return h.hexdigest()


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
        if np.isnan(x):
            return None
        return x
    except (TypeError, ValueError):
        return None


async def fetch_financial_docs(ticker: str) -> list[dict[str, Any]]:
    cfg = get_config()
    if cfg.financial_data_mode == "mock":
        return []

    def _pull() -> str:
        try:
            import yfinance as yf
        except Exception as exc:  # pragma: no cover
            logger.warning("yfinance import failed: %s", exc)
            return f"(yfinance import failed for {ticker})"

        as_of = datetime.now(timezone.utc).isoformat()
        try:
            tk = yf.Ticker(ticker)
        except Exception:
            return f"(yfinance could not initialize ticker={ticker})"

        info = getattr(tk, "info", None) or {}
        if not isinstance(info, dict):
            info = {}

        fields = {
            "trailingPE": _num(info.get("trailingPE")),
            "forwardPE": _num(info.get("forwardPE")),
            "marketCap": _num(info.get("marketCap")),
            "profitMargins": _num(info.get("profitMargins")),
            "operatingMargins": _num(info.get("operatingMargins")),
            "grossMargins": _num(info.get("grossMargins")),
            "returnOnEquity": _num(info.get("returnOnEquity")),
            "returnOnAssets": _num(info.get("returnOnAssets")),
            "revenueGrowth": _num(info.get("revenueGrowth")),
            "earningsGrowth": _num(info.get("earningsGrowth")),
            "freeCashflow": _num(info.get("freeCashflow")),
            "operatingCashflow": _num(info.get("operatingCashflow")),
            "debtToEquity": _num(info.get("debtToEquity")),
            "quickRatio": _num(info.get("quickRatio")),
            "currentRatio": _num(info.get("currentRatio")),
        }

        # Build a compact "evidence doc" for the LLM.
        def fmt(k: str, v: float | None) -> str:
            if v is None:
                return f"- {k}: —"
            if "Margins" in k or "profit" in k.lower() or "Growth" in k or "Ratio" in k:
                # Keep small decimals reasonable.
                if abs(v) <= 1.0:
                    return f"- {k}: {v:.3f}"
            return f"- {k}: {v:.4g}"

        lines = [
            f"Financial fundamentals snapshot (source: yfinance.info) for {ticker.upper()}",
            f"as_of_utc: {as_of}",
            "",
            "Key metrics:",
        ]
        for k, v in fields.items():
            lines.append(fmt(k, v))

        # Optional: hint on missingness to avoid hallucinating.
        missing = sum(1 for _, v in fields.items() if v is None)
        lines.append("")
        lines.append(f"Data completeness: {missing}/{len(fields)} metrics missing.")

        return "\n".join(lines)

    text = await asyncio.to_thread(_pull)
    return [
        {
            "id": _stable_id(ticker, "financials_yfinance"),
            "text": text,
            "metadata": {"ticker": ticker, "source_type": "live_financials_yfinance"},
        }
    ]

