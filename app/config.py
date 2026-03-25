from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class WeightConfig(BaseModel):
    source_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "earnings_call": 1.0,
            "financial_filings": 0.95,
            "news": 0.7,
            "social_media": 0.4,
            "macro": 0.75,
        }
    )
    recency_lambda: float = 0.08
    # How much to trust evidence completeness/grounding in signal weighting.
    evidence_quality_weight: float = 0.35
    # How much to trust timestamp freshness (based on whether context had dates).
    freshness_confidence_weight: float = 0.35


class RetrievalConfig(BaseModel):
    collection_name: str = "stock_documents"
    top_k: int = 5
    hyde_enabled: bool = True
    rerank_enabled: bool = False


class AppConfig(BaseModel):
    app_name: str = "stock-analyst"
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    chroma_dir: Path = Field(default_factory=lambda: Path("data/chroma"))
    sqlite_path: Path = Field(default_factory=lambda: Path("data/stock_analyst.db"))
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    tavily_api_key: str | None = None
    langchain_api_key: str | None = None
    langchain_project: str = "stock-analyst"
    langchain_tracing_v2: bool = True
    social_data_mode: str = "mock"
    financial_data_mode: str = "mock"
    news_data_mode: str = "mock"
    max_iterations: int = 2
    weights: WeightConfig = Field(default_factory=WeightConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    env_values = {
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "tavily_api_key": os.getenv("TAVILY_API_KEY"),
        "langchain_api_key": os.getenv("LANGCHAIN_API_KEY"),
        "langchain_project": os.getenv("LANGCHAIN_PROJECT", "stock-analyst"),
        "langchain_tracing_v2": os.getenv("LANGCHAIN_TRACING_V2", "true").lower() == "true",
        "social_data_mode": os.getenv("SOCIAL_DATA_MODE", "mock"),
        "financial_data_mode": os.getenv("FINANCIAL_DATA_MODE", "mock"),
        "news_data_mode": os.getenv("NEWS_DATA_MODE", "mock"),
    }
    config = AppConfig(**env_values)
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.chroma_dir.mkdir(parents=True, exist_ok=True)
    config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return config
