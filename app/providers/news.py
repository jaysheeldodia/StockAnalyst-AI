from __future__ import annotations

from app.config import get_config
from app.providers.base import DataProvider
from app.providers.mock_data import MOCK_SIGNALS
from app.live.social_news import fetch_news_docs
from app.llm.signals import generate_signals_with_llm


class NewsProvider(DataProvider):
    async def fetch(self, ticker: str, plan: dict) -> list[dict]:
        cfg = get_config()
        if cfg.news_data_mode == "mock":
            return MOCK_SIGNALS.get(ticker, {}).get("news", [])

        docs = await fetch_news_docs(ticker)
        if not docs:
            return []

        raw = await generate_signals_with_llm(
            agent_name="news_agent",
            ticker=ticker,
            retrieval_objective="recent company news and catalysts",
            retrieved_context=docs,
            plan=plan,
            iteration_count=0,
        )
        return raw or []
