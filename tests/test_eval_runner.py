from __future__ import annotations

from evals.lib.pricing import cost_usd, price_for
from evals.run_eval import Budget, load_rows, select_rows


def test_smoke_selects_one_answerable_case_per_ticker() -> None:
    rows = select_rows(load_rows(), "smoke", None)
    assert len(rows) == 5
    assert len({r["ticker"] for r in rows}) == 5
    assert not any(r["must_refuse"] for r in rows)


def test_max_cases_truncates() -> None:
    assert len(select_rows(load_rows(), "full", 7)) == 7


def test_budget_stops_when_estimate_passes_cap() -> None:
    budget = Budget(max_usd=0.05, est_analysis=0.02, est_judge=None)
    assert budget.allows("analysis")
    budget.add("analysis", 0.02)
    budget.add("analysis", 0.02)
    assert not budget.allows("analysis")


def test_budget_without_cap_always_allows() -> None:
    assert Budget(None, None, None).allows("judge")


def test_pricing_handles_dated_snapshots_and_unknown_models() -> None:
    assert price_for("gpt-4o-mini-2024-07-18") == price_for("gpt-4o-mini")
    assert cost_usd("gpt-4o-mini", 1_000_000, 1_000_000) == 0.75
    assert cost_usd("unknown-model", 10, 10) is None
    assert cost_usd("unknown-model", 0, 0) == 0.0
