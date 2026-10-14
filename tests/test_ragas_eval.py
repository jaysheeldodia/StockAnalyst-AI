from __future__ import annotations

import pytest

from app.evaluation.ragas_eval import CaseScores, score_case


def _fake_judge(question, answer, contexts, reference):
    assert reference != answer
    return {
        "faithfulness": 0.9,
        "answer_relevancy": 0.8,
        "context_precision": [0.7],
        "context_recall": float("nan"),
        "input_tokens": 120,
        "output_tokens": 30,
    }


def test_score_case_uses_injected_judge() -> None:
    scores = score_case(
        "What was revenue?", "Revenue was 10.", ["Revenue was 10."], "10", judge=_fake_judge
    )
    assert scores == CaseScores(
        faithfulness=0.9,
        answer_relevancy=0.8,
        context_precision=0.7,
        context_recall=None,
        input_tokens=120,
        output_tokens=30,
        error=None,
    )


@pytest.mark.parametrize("reference", ["", "   ", None])
def test_score_case_requires_reference(reference) -> None:
    with pytest.raises(ValueError, match="reference"):
        score_case("q", "a", ["c"], reference, judge=_fake_judge)


def test_score_case_requires_contexts() -> None:
    with pytest.raises(ValueError, match="context"):
        score_case("q", "a", [], "ref", judge=_fake_judge)


def test_score_case_records_judge_error() -> None:
    def broken(*_):
        raise RuntimeError("judge down")

    scores = score_case("q", "a", ["c"], "ref", judge=broken)
    assert scores.error == "RuntimeError: judge down"
    assert scores.faithfulness is None


def test_score_case_flags_empty_judge_output() -> None:
    scores = score_case("q", "a", ["c"], "ref", judge=lambda *_: {})
    assert scores.error == "Judge returned no scalar metrics"
