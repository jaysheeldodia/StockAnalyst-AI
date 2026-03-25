from __future__ import annotations

from typing import Any

from app.live.tavily_search import tavily_search_documents


async def fetch_news_docs(ticker: str) -> list[dict[str, Any]]:
    # Objective: "recent company news and catalysts"
    query = f"{ticker} stock recent news catalysts earnings guidance"
    return await tavily_search_documents(
        query=query,
        ticker=ticker,
        source_type="news_tavily",
        max_results=6,
        time_range="month",
    )


async def fetch_social_docs(ticker: str) -> list[dict[str, Any]]:
    # Objective: "social sentiment and retail investor narratives"
    # Use sources that are commonly indexable by web search.
    query = f"{ticker} stock sentiment reddit stocktwits"
    return await tavily_search_documents(
        query=query,
        ticker=ticker,
        source_type="social_tavily",
        max_results=6,
        time_range="month",
    )

