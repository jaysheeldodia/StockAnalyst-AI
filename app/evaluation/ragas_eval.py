from __future__ import annotations

import os

from app.storage.sqlite_store import SQLiteStore


def _coerce_metric(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if hasattr(val, "tolist"):
        return _coerce_metric(val.tolist())
    if isinstance(val, (list, tuple)):
        for item in val:
            c = _coerce_metric(item)
            if c is not None:
                return c
    return None


async def evaluate_and_store(
    ticker: str, report: str, contexts: list[str], reference: str | None = None
) -> None:
    try:
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, faithfulness
        from datasets import Dataset
    except ImportError:
        await SQLiteStore().save_evaluation(
            ticker,
            None,
            None,
            None,
            "Ragas or datasets not installed; evaluation skipped.",
        )
        return

    if not os.getenv("OPENAI_API_KEY"):
        await SQLiteStore().save_evaluation(
            ticker,
            None,
            None,
            None,
            "Ragas metrics require OPENAI_API_KEY; skipped.",
        )
        return

    if not contexts:
        await SQLiteStore().save_evaluation(
            ticker,
            None,
            None,
            None,
            "No contexts available for evaluation.",
        )
        return

    dataset = Dataset.from_dict(
        {
            "question": [f"Generate a stock analyst report for {ticker}"],
            "answer": [report],
            "contexts": [contexts],
            "ground_truth": [reference or report],
        }
    )
    try:
        results = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision])
    except Exception as exc:
        await SQLiteStore().save_evaluation(
            ticker,
            None,
            None,
            None,
            f"Ragas evaluation failed: {exc!s}",
        )
        return

    faith = _coerce_metric(results.get("faithfulness"))
    ar = _coerce_metric(results.get("answer_relevancy"))
    cp = _coerce_metric(results.get("context_precision"))
    note = "Evaluation complete."
    if faith is None and ar is None and cp is None:
        note = "Ragas returned no scalar metrics (see Ragas / model output)."
    elif faith is None or ar is None or cp is None:
        note = "Evaluation complete (partial metrics only)."

    await SQLiteStore().save_evaluation(
        ticker,
        faith,
        ar,
        cp,
        note,
    )
