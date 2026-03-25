from __future__ import annotations

from app.providers.base import DataProvider
from app.providers.mock_data import MOCK_SIGNALS


class MacroProvider(DataProvider):
    async def fetch(self, ticker: str, plan: dict) -> list[dict]:
        return MOCK_SIGNALS.get(ticker, {}).get("macro", [])
