from __future__ import annotations

from app.config import get_config
from app.providers.base import DataProvider
from app.providers.mock_data import MOCK_SIGNALS
from app.live.social_news import fetch_social_docs
from app.llm.signals import generate_signals_with_llm


class SentimentProvider(DataProvider):
    async def fetch(self, ticker: str, plan: dict) -> list[dict]:
        cfg = get_config()
        if cfg.social_data_mode == "mock":
            return MOCK_SIGNALS.get(ticker, {}).get("sentiment", [])

        docs = await fetch_social_docs(ticker)
        if not docs:
            return []

        raw = await generate_signals_with_llm(
            agent_name="sentiment_agent",
            ticker=ticker,
            retrieval_objective="social sentiment and retail investor narratives",
            retrieved_context=docs,
            plan=plan,
            iteration_count=0,
        )
        return raw or []
