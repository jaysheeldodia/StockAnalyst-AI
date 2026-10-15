from __future__ import annotations

import pytest
import sqlite3
from pathlib import Path

from app.bootstrap import main as bootstrap_main
from app.config import get_config
from app.services.analysis_service import AnalysisService


@pytest.fixture
def no_llm(monkeypatch: pytest.MonkeyPatch):
    # get_config() is cached; without clearing it, a key loaded earlier from .env reaches the LLM.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_config.cache_clear()
    yield
    get_config.cache_clear()


@pytest.mark.asyncio
async def test_analysis_workflow_generates_report(
    monkeypatch: pytest.MonkeyPatch, no_llm: None
) -> None:

    async def _fake_market(ticker: str) -> dict:
        return {
            "as_of_utc": "2025-01-01T00:00:00+00:00",
            "source": "test",
            "ticker": ticker.upper(),
            "error": None,
            "quote": {
                "price": 100.0,
                "previous_close": 99.0,
                "currency": "USD",
                "name": "Test Co",
                "week_52_high": 110.0,
                "week_52_low": 90.0,
            },
            "profile": {"sector": "Technology", "industry": "Software"},
            "metrics": {
                "pe_trailing": 25.0,
                "market_cap": 1e12,
                "distance_from_52w_high_pct": -9.09,
                "position_in_52w_range_pct": 50.0,
                "ytd_return_pct": 5.0,
            },
            "peer_context": "Test peer context.",
        }

    monkeypatch.setattr(
        "app.graph.market_snapshot.fetch_market_snapshot_async",
        _fake_market,
    )

    cfg = get_config()
    db_path: Path = cfg.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    bootstrap_main()
    service = AnalysisService()
    await service.setup()

    with sqlite3.connect(db_path) as conn:
        # Measure baseline count before the run to avoid relying on a dev DB state.
        cur = conn.execute("SELECT COUNT(*) FROM predictions WHERE ticker = ?", ("AAPL",))
        count_before = cur.fetchone()[0]

    result = await service.analyze("AAPL", horizon="12m")
    assert result["ticker"] == "AAPL"
    assert result["horizon"] == "12m"
    assert result["report"]
    assert result["weighted_signals"]
    assert "confidence_score" in result["final_thesis"]
    assert result["market_snapshot"]["source"] == "test"
    assert "audit" in result

    # Valuation range should be computed deterministically from the market snapshot.
    ft = result["final_thesis"]
    assert ft.get("fair_value_low") is not None
    assert ft.get("fair_value_base") is not None
    assert ft.get("fair_value_high") is not None
    assert ft.get("implied_return_base_pct") is not None

    # Prediction baseline should be persisted for calibration.
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM predictions WHERE ticker = ?", ("AAPL",))
        count_after = cur.fetchone()[0]
        assert count_after > count_before
