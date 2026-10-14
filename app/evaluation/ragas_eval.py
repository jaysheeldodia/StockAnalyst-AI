from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

from app.storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

METRIC_NAMES = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")

# A judge takes (question, answer, contexts, reference) and returns a mapping with any of
# METRIC_NAMES plus optional "input_tokens" / "output_tokens".
Judge = Callable[[str, str, list[str], str], Mapping[str, Any]]


@dataclass(slots=True)
class CaseScores:
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _coerce_metric(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        f = float(val)
        return None if f != f else f
    if hasattr(val, "tolist"):
        return _coerce_metric(val.tolist())
    if isinstance(val, (list, tuple)):
        for item in val:
            c = _coerce_metric(item)
            if c is not None:
                return c
    return None


class RagasJudge:
    """Default judge: one Ragas evaluation of a single sample, exceptions raised."""

    def __init__(self, model: str | None = None, embedding_model: str | None = None) -> None:
        self.model = model or os.getenv("EVAL_JUDGE_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.embedding_model = embedding_model or os.getenv(
            "EVAL_JUDGE_EMBEDDING_MODEL", "text-embedding-3-small"
        )

    def __call__(
        self, question: str, answer: str, contexts: list[str], reference: str
    ) -> dict[str, Any]:
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.cost import get_token_usage_for_openai
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        dataset = EvaluationDataset(
            samples=[
                SingleTurnSample(
                    user_input=question,
                    response=answer,
                    retrieved_contexts=contexts,
                    reference=reference,
                )
            ]
        )
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=LangchainLLMWrapper(ChatOpenAI(model=self.model, temperature=0)),
            embeddings=LangchainEmbeddingsWrapper(OpenAIEmbeddings(model=self.embedding_model)),
            token_usage_parser=get_token_usage_for_openai,
            raise_exceptions=True,
            show_progress=False,
        )
        row = result.scores[0] if result.scores else {}
        usage = result.total_tokens()
        if isinstance(usage, list):
            in_tok = sum(u.input_tokens for u in usage)
            out_tok = sum(u.output_tokens for u in usage)
        else:
            in_tok, out_tok = usage.input_tokens, usage.output_tokens
        return {**{name: row.get(name) for name in METRIC_NAMES}, "input_tokens": in_tok, "output_tokens": out_tok}


def score_case(
    question: str,
    answer: str,
    contexts: list[str],
    reference: str,
    *,
    judge: Judge | None = None,
) -> CaseScores:
    """Score one case. Invalid inputs raise; judge failures are recorded in ``error``."""
    if not question or not question.strip():
        raise ValueError("score_case requires a non-empty question")
    if not reference or not reference.strip():
        raise ValueError("score_case requires a real reference; the answer cannot be its own")
    if not contexts:
        raise ValueError("score_case requires at least one retrieved context")

    judge = judge or RagasJudge()
    try:
        raw = judge(question, answer, contexts, reference)
    except Exception as exc:
        logger.exception("Judge failed")
        return CaseScores(error=f"{type(exc).__name__}: {exc}")

    scores = CaseScores(
        **{name: _coerce_metric(raw.get(name)) for name in METRIC_NAMES},
        input_tokens=int(raw.get("input_tokens") or 0),
        output_tokens=int(raw.get("output_tokens") or 0),
    )
    if all(getattr(scores, name) is None for name in METRIC_NAMES):
        scores.error = "Judge returned no scalar metrics"
    return scores


async def evaluate_and_store(
    ticker: str,
    report: str,
    contexts: list[str],
    reference: str | None = None,
    question: str | None = None,
) -> CaseScores | None:
    store = SQLiteStore()
    if not reference:
        await store.save_evaluation(
            ticker, None, None, None, "No reference answer supplied; Ragas evaluation skipped."
        )
        return None
    if not os.getenv("OPENAI_API_KEY"):
        await store.save_evaluation(
            ticker, None, None, None, "Ragas metrics require OPENAI_API_KEY; skipped."
        )
        return None
    if not contexts:
        await store.save_evaluation(
            ticker, None, None, None, "No contexts available for evaluation."
        )
        return None

    scores = await asyncio.to_thread(
        score_case,
        question or f"Generate a stock analyst report for {ticker}",
        report,
        contexts,
        reference,
    )
    if scores.error:
        note = f"Ragas evaluation failed: {scores.error}"
    elif None in (scores.faithfulness, scores.answer_relevancy, scores.context_precision):
        note = "Evaluation complete (partial metrics only)."
    else:
        note = "Evaluation complete."
    await store.save_evaluation(
        ticker, scores.faithfulness, scores.answer_relevancy, scores.context_precision, note
    )
    return scores
