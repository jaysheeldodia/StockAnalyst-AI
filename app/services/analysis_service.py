from __future__ import annotations

from collections.abc import AsyncIterator

from app.evaluation.ragas_eval import evaluate_and_store
from app.graph.workflow import build_graph
from app.observability import configure_langsmith
from app.state import GraphState, initial_state
from app.storage.sqlite_store import SQLiteStore


class AnalysisService:
    def __init__(self) -> None:
        configure_langsmith()
        self.graph = build_graph()
        self.store = SQLiteStore()

    async def setup(self) -> None:
        await self.store.initialize()

    async def finalize_evaluation(self, final_state: GraphState) -> None:
        contexts: list[str] = []
        for result in final_state["raw_results"]:
            contexts.extend(item["text"] for item in result.get("retrieved_context", []))
        await evaluate_and_store(final_state["ticker"], final_state["report"], contexts)

        # Persist a baseline prediction snapshot for lightweight calibration.
        ms = final_state.get("market_snapshot") or {}
        q = ms.get("quote") or {}
        as_of = ms.get("as_of_utc") or ""

        weighted = final_state.get("weighted_signals") or []
        bull = sum(
            float(s.get("score", 0))
            for s in weighted
            if (s.get("direction") or "").lower() == "bullish"
        )
        bear = sum(
            float(s.get("score", 0))
            for s in weighted
            if (s.get("direction") or "").lower() == "bearish"
        )
        net = bull - bear
        scale = bull + bear + 1e-9
        norm = net / scale
        if norm > 0.12:
            recommendation = "Buy"
        elif norm < -0.12:
            recommendation = "Sell"
        else:
            recommendation = "Hold"

        thesis = final_state.get("final_thesis") or {}
        await self.store.save_prediction_baseline(
            ticker=final_state["ticker"],
            horizon=final_state.get("horizon", "12m"),
            as_of_utc=as_of,
            entry_price=q.get("price"),
            recommendation=recommendation,
            confidence_score=thesis.get("confidence_score"),
            fair_value_low=thesis.get("fair_value_low"),
            fair_value_base=thesis.get("fair_value_base"),
            fair_value_high=thesis.get("fair_value_high"),
            predicted_return_base_pct=thesis.get("implied_return_base_pct"),
        )

    async def analyze(self, ticker: str, horizon: str = "12m") -> GraphState:
        await self.setup()
        final_state = await self.graph.ainvoke(initial_state(ticker, horizon=horizon))
        await self.finalize_evaluation(final_state)
        return final_state

    async def stream_analysis(self, ticker: str, horizon: str = "12m") -> AsyncIterator[dict]:
        await self.setup()
        final_state: GraphState | None = None
        async for event in self.graph.astream(
            initial_state(ticker, horizon=horizon), stream_mode="values"
        ):
            final_state = event
            yield event

        # Persist baseline snapshot + evaluation after streaming completes.
        # (Streamlit UI historically called finalize_evaluation itself; we keep this
        # centralized so the web UI also persists calibration data.)
        if final_state:
            await self.finalize_evaluation(final_state)
