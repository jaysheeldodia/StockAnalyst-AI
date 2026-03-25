from __future__ import annotations

from typing import Protocol


class DataProvider(Protocol):
    async def fetch(self, ticker: str, plan: dict) -> list[dict]:
        ...
