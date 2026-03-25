from __future__ import annotations

from datetime import datetime, timedelta, timezone


def iso(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


MOCK_SIGNALS: dict[str, dict[str, list[dict]]] = {
    "AAPL": {
        "news": [
            {
                "claim": "iPhone replacement demand is improving in premium segments.",
                "evidence": "Channel checks indicate stronger-than-expected premium smartphone upgrades.",
                "source": "Tavily: premium smartphone demand article",
                "confidence": 0.72,
                "timestamp": iso(3),
                "direction": "bullish",
                "topic": "consumer demand",
            },
            {
                "claim": "Regulatory pressure on app store economics remains elevated in key markets.",
                "evidence": "Policy updates continue to scrutinize app distribution fees and exclusivity.",
                "source": "Tavily: app store regulation roundup",
                "confidence": 0.68,
                "timestamp": iso(5),
                "direction": "bearish",
                "topic": "services regulation",
            },
        ],
        "transcript": [
            {
                "claim": "Management highlighted margin support from services mix and silicon efficiency.",
                "evidence": "Recent earnings remarks emphasized services growth and product cost discipline.",
                "source": "Q1 earnings transcript",
                "confidence": 0.86,
                "timestamp": iso(15),
                "direction": "bullish",
                "topic": "gross margin",
            }
        ],
        "financials": [
            {
                "claim": "Free cash flow remains resilient relative to large-cap peers.",
                "evidence": "Operating cash generation and buyback capacity remain strong.",
                "source": "Financial metrics API",
                "confidence": 0.83,
                "timestamp": iso(10),
                "direction": "bullish",
                "topic": "cash flow",
            },
            {
                "claim": "Revenue growth remains moderate versus historical hardware cycles.",
                "evidence": "Top-line expansion has not returned to prior super-cycle levels.",
                "source": "Financial metrics API",
                "confidence": 0.64,
                "timestamp": iso(10),
                "direction": "neutral",
                "topic": "growth profile",
            },
        ],
        "sentiment": [
            {
                "claim": "Retail sentiment is constructive on AI-enabled device upgrades.",
                "evidence": "Social discussion clusters around on-device AI and ecosystem lock-in.",
                "source": "Reddit/Twitter mock stream",
                "confidence": 0.55,
                "timestamp": iso(1),
                "direction": "bullish",
                "topic": "ai devices",
            },
            {
                "claim": "Some social chatter questions the sustainability of premium pricing.",
                "evidence": "Posts point to longer handset replacement cycles and macro pressure.",
                "source": "Reddit/Twitter mock stream",
                "confidence": 0.44,
                "timestamp": iso(1),
                "direction": "bearish",
                "topic": "consumer demand",
            },
        ],
        "macro": [
            {
                "claim": "Easing rate expectations could support valuation stability for mega-cap growth.",
                "evidence": "Lower discount-rate pressure tends to help long-duration cash flow names.",
                "source": "Macro economics digest",
                "confidence": 0.62,
                "timestamp": iso(2),
                "direction": "bullish",
                "topic": "valuation",
            }
        ],
    }
}


MOCK_DOCUMENTS = [
    {
        "id": "aapl_transcript_q1",
        "text": (
            "Apple management emphasized services growth, active device base expansion, "
            "and margin resilience from product mix and silicon efficiency."
        ),
        "metadata": {"ticker": "AAPL", "source_type": "earnings_call"},
    },
    {
        "id": "aapl_filings",
        "text": (
            "Apple filings show strong cash generation, capital returns, and moderate "
            "revenue growth relative to earlier hardware super-cycles."
        ),
        "metadata": {"ticker": "AAPL", "source_type": "financial_filings"},
    },
]
