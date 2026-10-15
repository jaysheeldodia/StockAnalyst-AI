"""USD prices per 1M tokens, Standard tier.

Source: https://platform.openai.com/docs/pricing (accessed 2026-10-14).
"""

from __future__ import annotations

PRICING_SOURCE = "https://platform.openai.com/docs/pricing"
PRICING_ACCESSED = "2026-10-14"

# model -> (input USD / 1M tokens, output USD / 1M tokens)
PRICES_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "text-embedding-3-small": (0.02, 0.0),
}


def price_for(model: str) -> tuple[float, float] | None:
    """Look up a model, accepting dated snapshots such as gpt-4o-mini-2024-07-18."""
    if model in PRICES_PER_1M:
        return PRICES_PER_1M[model]
    matches = [m for m in PRICES_PER_1M if model.startswith(m + "-")]
    return PRICES_PER_1M[max(matches, key=len)] if matches else None


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Dollar cost of a call, or None when the model has no known price."""
    if not input_tokens and not output_tokens:
        return 0.0
    price = price_for(model)
    if price is None:
        return None
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000
