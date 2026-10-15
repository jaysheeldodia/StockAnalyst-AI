from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from app.config import get_config
from app.retrieval.hyde import build_hyde_query
from app.storage.chroma_store import ChromaStore
from app.live.financials import fetch_financial_docs
from app.live.social_news import fetch_news_docs, fetch_social_docs


def _text_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


class RetrievalService:
    def __init__(self, store: ChromaStore | None = None) -> None:
        self.config = get_config()
        self.store = store or ChromaStore()

    def retrieve(self, ticker: str, objective: str) -> list[dict[str, Any]]:
        queries = [f"{ticker} {objective}"]
        if self.config.retrieval.hyde_enabled:
            queries.append(build_hyde_query(ticker, objective))
        results = self.store.query(query_texts=queries, top_k=self.config.retrieval.top_k)
        if self.config.retrieval.rerank_enabled:
            results = sorted(results, key=lambda item: item["distance"])
        return results

    async def aretrieve(self, ticker: str, objective: str) -> list[dict[str, Any]]:
        """
        Async retrieval that can augment Chroma context with live web/fundamental data.
        """
        queries = [f"{ticker} {objective}"]
        if self.config.retrieval.hyde_enabled:
            queries.append(build_hyde_query(ticker, objective))

        base_results = await asyncio.to_thread(
            self.store.query, query_texts=queries, top_k=self.config.retrieval.top_k
        )

        obj = (objective or "").lower()
        live_docs: list[dict[str, Any]] = []
        # Keyword-based routing keeps it simple and avoids changing the graph interface.
        if self.config.news_data_mode != "mock" and ("news" in obj or "catalyst" in obj):
            live_docs.extend(await fetch_news_docs(ticker))
        if self.config.financial_data_mode != "mock" and ("financial" in obj or "cash flow" in obj):
            live_docs.extend(await fetch_financial_docs(ticker))
        if self.config.social_data_mode != "mock" and ("sentiment" in obj or "social" in obj):
            live_docs.extend(await fetch_social_docs(ticker))

        # Ensure schema compatibility with existing RAG formatter.
        augmented: list[dict[str, Any]] = [
            {
                "id": d.get("id") or _text_id(d.get("text") or ""),
                "text": d.get("text") or "",
                "metadata": d.get("metadata") or {},
                "distance": d.get("distance"),
            }
            for d in live_docs
        ]
        for a in augmented:
            if a.get("distance") is None:
                # Favor live chunks over vector-store results.
                # (Chroma distances may tie at 0.0, so use a negative score.)
                a["distance"] = -1.0

        combined = list(base_results) + augmented
        if self.config.retrieval.rerank_enabled:
            combined = sorted(combined, key=lambda item: item.get("distance", 0.0))

        # Trim to top_k to keep context size bounded.
        combined.sort(key=lambda item: item.get("distance", 0.0))
        return combined[: self.config.retrieval.top_k]
