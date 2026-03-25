from __future__ import annotations

from langchain_openai import ChatOpenAI

from app.config import get_config


def is_llm_configured() -> bool:
    return bool(get_config().openai_api_key)


def get_chat_model() -> ChatOpenAI | None:
    cfg = get_config()
    if not cfg.openai_api_key:
        return None
    return ChatOpenAI(
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        temperature=0.2,
    )
