from __future__ import annotations

from datetime import datetime, timezone

from app.config import get_config
from app.version import get_app_version


def build_audit_metadata(horizon: str, market_snapshot: dict | None) -> dict:
    cfg = get_config()
    ms = market_snapshot or {}
    return {
        "app_version": get_app_version(),
        "openai_model": cfg.openai_model if cfg.openai_api_key else None,
        "horizon": horizon,
        "market_data_source": ms.get("source"),
        "market_data_as_of_utc": ms.get("as_of_utc"),
        "market_data_error": ms.get("error"),
        "news_data_mode": cfg.news_data_mode,
        "financial_data_mode": cfg.financial_data_mode,
        "social_data_mode": cfg.social_data_mode,
        "tavily_api_configured": bool(cfg.tavily_api_key),
        "audit_created_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def finalize_audit(audit: dict) -> dict:
    out = dict(audit)
    out["report_completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    return out
