from __future__ import annotations

import os
from functools import wraps
from typing import Any, Awaitable, Callable

from app.config import get_config

try:
    from langsmith import traceable
except ImportError:  # pragma: no cover
    traceable = None


def configure_langsmith() -> None:
    config = get_config()
    if config.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = config.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = config.langchain_project
        os.environ["LANGCHAIN_TRACING_V2"] = str(config.langchain_tracing_v2).lower()
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"


def traced(name: str) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        if traceable is None:
            @wraps(func)
            async def fallback(*args: Any, **kwargs: Any) -> Any:
                return await func(*args, **kwargs)

            return fallback

        @traceable(name=name)
        @wraps(func)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        return wrapped

    return decorator
