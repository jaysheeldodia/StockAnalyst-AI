from __future__ import annotations

import copy

import pytest

from evals.compare_baseline import compare
from evals.lib.report import DETERMINISTIC, JUDGED


def _result(**overrides) -> dict:
    metrics = {n: {"value": 0.5, "n": 10, "reason": None} for n in DETERMINISTIC + JUDGED}
    summary = {
        "metrics": metrics,
        "latency_s": {"p50": 1.0, "p95": 2.0, "p99": 3.0, "n": 5},
        "mean_usd_per_report": {"value": 0.01, "n": 5},
        "mean_tokens_per_report": {"value": 1000.0, "n": 5},
        "failure_rate": {"value": 0.0, "n": 10, "failures": 0},
    }
    result = {"summary": summary}
    for path, value in overrides.items():
        node = summary
        *parents, leaf = path.split(".")
        for p in parents:
            node = node[p]
        node[leaf] = value
    return result


def _status(rows, metric) -> str:
    return next(r[-1] for r in rows if r[0] == metric)


def test_identical_results_pass_and_print_every_metric() -> None:
    base = _result()
    rows, failed = compare(copy.deepcopy(base), base)
    assert not failed
    names = {r[0] for r in rows}
    assert set(DETERMINISTIC + JUDGED) <= names
    assert {"latency_p95_s", "mean_usd_per_report", "case_exceptions"} <= names


@pytest.mark.parametrize(
    "overrides,metric",
    [
        ({"metrics.faithfulness": {"value": 0.469, "n": 10}}, "faithfulness"),
        ({"metrics.unsupported_number_rate": {"value": 0.521, "n": 10}}, "unsupported_number_rate"),
        ({"latency_s.p95": 2.41}, "latency_p95_s"),
        ({"mean_usd_per_report": {"value": 0.0121, "n": 5}}, "mean_usd_per_report"),
        ({"failure_rate": {"value": 0.1, "n": 10, "failures": 1}}, "case_exceptions"),
    ],
)
def test_each_gate_fails(overrides, metric) -> None:
    rows, failed = compare(_result(**overrides), _result())
    assert failed
    assert _status(rows, metric) == "FAIL"


@pytest.mark.parametrize(
    "overrides",
    [
        {"metrics.faithfulness": {"value": 0.471, "n": 10}},
        {"metrics.unsupported_number_rate": {"value": 0.519, "n": 10}},
        {"latency_s.p95": 2.39},
        {"mean_usd_per_report": {"value": 0.0119, "n": 5}},
        {"metrics.citation_coverage": {"value": 0.0, "n": 10}},
    ],
)
def test_changes_within_tolerance_pass(overrides) -> None:
    _, failed = compare(_result(**overrides), _result())
    assert not failed


def test_missing_judged_metric_is_not_gated() -> None:
    rows, failed = compare(_result(**{"metrics.faithfulness": {"value": None, "n": 0}}), _result())
    assert not failed
    assert _status(rows, "faithfulness") == "n/a"


def test_cost_rise_from_zero_fails() -> None:
    base = _result(mean_usd_per_report={"value": 0.0, "n": 5})
    rows, failed = compare(_result(), base)
    assert failed and _status(rows, "mean_usd_per_report") == "FAIL"
