from __future__ import annotations

from app.config import get_config
from app.providers.base import DataProvider
from app.providers.mock_data import MOCK_SIGNALS
from app.live.financials import fetch_financial_docs
from app.llm.signals import generate_signals_with_llm


class FinancialsProvider(DataProvider):
    async def fetch(self, ticker: str, plan: dict) -> list[dict]:
        cfg = get_config()
        if cfg.financial_data_mode == "mock":
            return MOCK_SIGNALS.get(ticker, {}).get("financials", [])

        docs = await fetch_financial_docs(ticker)
        if not docs:
            return []

        raw = await generate_signals_with_llm(
            agent_name="financials_agent",
            ticker=ticker,
            retrieval_objective="financial filings, cash flow, and profitability",
            retrieved_context=docs,
            plan=plan,
            iteration_count=0,
        )
        return raw or []
