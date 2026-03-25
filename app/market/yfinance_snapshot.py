from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
        if x != x:  # NaN
            return None
        return x
    except (TypeError, ValueError):
        return None


def fetch_market_snapshot(ticker: str) -> dict[str, Any]:
    """Pull quote, profile, and computed metrics via yfinance (sync)."""
    as_of = datetime.now(timezone.utc).isoformat()
    out: dict[str, Any] = {
        "as_of_utc": as_of,
        "source": "yfinance",
        "ticker": ticker.upper().strip(),
        "error": None,
        "quote": {},
        "profile": {},
        "metrics": {},
        "peer_context": "",
    }
    try:
        import yfinance as yf
    except ImportError:
        out["error"] = "yfinance not installed"
        return out

    try:
        tk = yf.Ticker(ticker)
        info = getattr(tk, "info", None) or {}
        if not isinstance(info, dict):
            info = {}

        price = None
        try:
            fast = tk.fast_info
            if isinstance(fast, dict):
                price = _num(fast.get("last_price"))
            else:
                price = _num(getattr(fast, "last_price", None))
        except Exception:
            pass
        price = price or _num(info.get("currentPrice"))
        price = price or _num(info.get("regularMarketPrice"))
        prev = _num(info.get("previousClose"))
        hi = _num(info.get("fiftyTwoWeekHigh"))
        lo = _num(info.get("fiftyTwoWeekLow"))

        name = info.get("longName") or info.get("shortName") or ticker.upper()
        sector = info.get("sector") or "—"
        industry = info.get("industry") or "—"
        currency = info.get("currency") or "USD"

        trailing_pe = _num(info.get("trailingPE"))
        forward_pe = _num(info.get("forwardPE"))
        pe = trailing_pe if trailing_pe is not None else forward_pe
        mcap = _num(info.get("marketCap"))

        # Optional fundamentals for lightweight valuation heuristics.
        profit_margins = _num(info.get("profitMargins"))
        operating_margins = _num(info.get("operatingMargins"))
        gross_margins = _num(info.get("grossMargins"))
        revenue_growth = _num(info.get("revenueGrowth"))
        earnings_growth = _num(info.get("earningsGrowth"))
        free_cashflow = _num(info.get("freeCashflow"))
        debt_to_equity = _num(info.get("debtToEquity"))
        return_on_equity = _num(info.get("returnOnEquity"))

        dist_hi = None
        range_pos = None
        if price is not None and hi is not None and hi > 0:
            dist_hi = (price / hi - 1.0) * 100.0
        if price is not None and hi is not None and lo is not None and hi > lo:
            range_pos = (price - lo) / (hi - lo) * 100.0

        ytd_ret = None
        try:
            hist = tk.history(period="ytd", auto_adjust=True)
            if hist is not None and len(hist) > 0 and price is not None:
                first_close = float(hist["Close"].iloc[0])
                if first_close > 0:
                    ytd_ret = (float(price) / first_close - 1.0) * 100.0
        except Exception:
            logger.debug("YTD history unavailable for %s", ticker, exc_info=True)

        out["quote"] = {
            "price": price,
            "previous_close": prev,
            "currency": currency,
            "name": name,
            "week_52_high": hi,
            "week_52_low": lo,
        }
        out["profile"] = {
            "sector": sector,
            "industry": industry,
        }
        out["metrics"] = {
            "pe_trailing": trailing_pe,
            "pe_forward": forward_pe,
            "market_cap": mcap,
            "distance_from_52w_high_pct": dist_hi,
            "position_in_52w_range_pct": range_pos,
            "ytd_return_pct": ytd_ret,
            "profit_margins": profit_margins,
            "operating_margins": operating_margins,
            "gross_margins": gross_margins,
            "revenue_growth": revenue_growth,
            "earnings_growth": earnings_growth,
            "free_cashflow": free_cashflow,
            "debt_to_equity": debt_to_equity,
            "return_on_equity": return_on_equity,
        }
        out["peer_context"] = (
            f"Sector **{sector}**, industry **{industry}**. "
            "For relative valuation, compare against large-cap peers in the same GICS sector/industry "
            "(peer list not auto-generated)."
        )
        if price is None and not info:
            out["error"] = "No market data returned (check ticker symbol)."
    except Exception as exc:
        logger.exception("yfinance fetch failed for %s", ticker)
        out["error"] = str(exc)

    return out


async def fetch_market_snapshot_async(ticker: str) -> dict[str, Any]:
    return await asyncio.to_thread(fetch_market_snapshot, ticker)
