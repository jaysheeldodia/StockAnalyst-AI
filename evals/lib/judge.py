"""Judged layer: Ragas scores for one case, priced."""

from __future__ import annotations

from typing import Any

from app.evaluation.ragas_eval import METRIC_NAMES, Judge, RagasJudge, score_case
from evals.lib.pricing import cost_usd


def make_judge() -> RagasJudge:
    return RagasJudge()


def judge_case(
    *,
    question: str,
    answer: str,
    contexts: list[str],
    reference: str,
    judge: Judge | RagasJudge,
) -> dict[str, Any]:
    """Score one case. Never raises for judge failures; they land in ``judge_error``."""
    if not contexts:
        return {
            **{name: None for name in METRIC_NAMES},
            "judge_input_tokens": 0,
            "judge_output_tokens": 0,
            "judge_cost_usd": 0.0,
            "judge_error": "no retrieved contexts",
        }
    scores = score_case(question, answer, contexts, reference, judge=judge)
    model = getattr(judge, "model", "unknown")
    return {
        **{name: getattr(scores, name) for name in METRIC_NAMES},
        "judge_input_tokens": scores.input_tokens,
        "judge_output_tokens": scores.output_tokens,
        "judge_cost_usd": cost_usd(model, scores.input_tokens, scores.output_tokens),
        "judge_error": scores.error,
    }
