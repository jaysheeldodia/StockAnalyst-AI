from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.analysis_service import AnalysisService


async def main() -> None:
    service = AnalysisService()
    result = await service.analyze("AAPL", horizon="12m")
    print(json.dumps(result["plan"], indent=2))
    print()
    print(json.dumps(result.get("market_snapshot", {}), indent=2, default=str))
    print()
    print(result["report"])


if __name__ == "__main__":
    asyncio.run(main())
