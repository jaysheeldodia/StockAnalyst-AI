from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import main as api_main
from app.api.schemas import AnalyzeResponse, retrieval_from_raw_results


def _state() -> dict:
    return {
        "ticker": "AAPL",
        "horizon": "12m",
        "plan": {},
        "market_snapshot": {},
        "audit": {},
        "raw_results": [
            {
                "agent_name": "news_agent",
                "retrieved_context": [
                    {"id": "c1", "text": "alpha", "metadata": {"url": "https://x"}, "distance": 0.2},
                    {"text": "beta", "metadata": {}, "distance": None},
                ],
            },
            {"agent_name": "macro_agent", "retrieved_context": [{"id": "c1", "text": "alpha"}]},
        ],
        "signals": [],
        "weighted_signals": [],
        "contradictions": [],
        "final_thesis": {},
        "report": "r",
        "iteration_count": 0,
    }


def test_retrieval_flattens_and_dedupes() -> None:
    chunks = retrieval_from_raw_results(_state()["raw_results"])
    assert [c.chunk_id for c in chunks][0] == "c1"
    assert len(chunks) == 2
    assert chunks[0].source_url == "https://x"
    assert chunks[0].score == 0.2
    assert chunks[1].score is None and len(chunks[1].chunk_id) == 12


def test_response_without_retrieval_is_backward_compatible() -> None:
    assert AnalyzeResponse(**_state()).retrieval == []


def test_analyze_endpoint_returns_retrieval(monkeypatch) -> None:
    async def fake_analyze(ticker: str, horizon: str = "12m") -> dict:
        return _state()

    monkeypatch.setattr(api_main.service, "analyze", fake_analyze)
    body = TestClient(api_main.app).post("/analyze", json={"ticker": "AAPL"}).json()
    assert [c["chunk_id"] for c in body["retrieval"]][0] == "c1"
    assert body["report"] == "r"
