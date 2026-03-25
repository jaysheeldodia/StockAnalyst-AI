from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from app.config import get_config

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


def _stable_id(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8", errors="ignore"))
        h.update(b"\x1f")
    return h.hexdigest()


async def tavily_search_documents(
    *,
    query: str,
    ticker: str,
    source_type: str,
    max_results: int = 6,
    time_range: str = "month",
) -> list[dict[str, Any]]:
    """
    Returns Tavily results mapped to "document chunks" for RAG context.
    """

    cfg = get_config()
    if cfg.news_data_mode == "mock" and source_type.startswith("news_"):
        return []
    if cfg.social_data_mode == "mock" and source_type.startswith("social_"):
        return []

    if not cfg.tavily_api_key:
        logger.warning("Tavily API key missing; cannot fetch live docs.")
        return []

    payload = {
        "api_key": cfg.tavily_api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "time_range": time_range,
        # Keep response size small; we just need snippets + URLs.
        "include_answer": False,
        "include_raw_content": False,
    }

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            resp = await client.post(TAVILY_API_URL, json=payload, headers={"Content-Type": "application/json"})
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logger.exception("Tavily request failed (query=%r)", query)
        return []

    results = data.get("results") or data.get("data") or []
    docs: list[dict[str, Any]] = []
    for r in results[:max_results]:
        title = r.get("title") or ""
        url = r.get("url") or r.get("source") or ""
        content = r.get("content") or r.get("snippet") or ""
        if not content and not title:
            continue

        # Keep each chunk compact: title + URL + short snippet.
        text = "\n".join(
            [
                f"Title: {title}".strip(),
                f"URL: {url}".strip(),
                content.strip(),
            ]
        ).strip()

        published_at = (
            r.get("published_date")
            or r.get("publishedDate")
            or r.get("date_published")
            or r.get("datePublished")
            or r.get("date")
            or r.get("created_at")
            or r.get("createdAt")
        )

        docs.append(
            {
                "id": _stable_id(ticker, source_type, url, title),
                "text": text,
                "metadata": {
                    "ticker": ticker,
                    "source_type": source_type,
                    "url": url,
                    "title": title,
                    "published_at": published_at,
                },
            }
        )

    return docs

