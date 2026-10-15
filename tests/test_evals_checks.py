from __future__ import annotations

import pytest

from app.legal.disclaimer import RESEARCH_DISCLAIMER
from evals.lib import checks

CHUNKS = [
    "Apple Inc. (AAPL) Form 10-K, fiscal year 2025: total revenue was $416.16 billion, "
    "compared with $391.04 billion in fiscal 2024, a year-over-year change of 6.4%.",
    "Apple Inc. (AAPL) balance sheet: shareholders' equity was $73.73 billion.",
]
APPENDIX = "\n\n## Market snapshot (third-party data)\n| Last price | 342.96 USD |\n"


def _report(body: str, disclaimer: bool = True) -> str:
    return body + APPENDIX + ("\n" + RESEARCH_DISCLAIMER if disclaimer else "")


# --- number extraction -----------------------------------------------------------------


def test_extract_numbers_skips_years_dates_and_labels() -> None:
    nums = checks.extract_numbers(
        "In FY2025 (2025-09-27) Apple filed its 10-K; revenue was $416.16 billion, up 6.4% "
        "versus 2024, near the 52-week high."
    )
    assert [n.text for n in nums] == ["$416.16 billion", "6.4%"]


def test_numbers_match_across_units_and_rounding() -> None:
    a = checks.extract_numbers("$416.2 billion")[0]
    b = checks.extract_numbers("416,161 million")[0]
    assert checks.numbers_match(a, b)
    assert not checks.numbers_match(a, checks.extract_numbers("$391.04 billion")[0])


# --- citation_coverage -----------------------------------------------------------------


def test_citation_coverage_passes_when_claims_are_grounded() -> None:
    body = (
        "## Executive Summary\n"
        "- Apple total revenue was $416.16 billion in fiscal 2025.\n"
        "- Revenue grew 6.4% year over year.\n"
    )
    assert checks.citation_coverage(_report(body), CHUNKS) == 1.0


def test_citation_coverage_fails_when_claims_are_unsupported() -> None:
    body = (
        "## Executive Summary\n"
        "- Apple total revenue was $416.16 billion in fiscal 2025.\n"
        "- Wearables margin expanded sharply on tariff relief in Vietnam.\n"
    )
    assert checks.citation_coverage(_report(body), CHUNKS) == 0.5


def test_citation_coverage_is_none_without_claims() -> None:
    assert checks.citation_coverage(_report("## Summary\nNo view."), CHUNKS) is None


# --- unsupported_number_rate -----------------------------------------------------------


def test_unsupported_number_rate_zero_when_all_numbers_retrieved() -> None:
    body = "Revenue reached $416.2 billion (+6.4%), and equity was $73.73 billion."
    assert checks.unsupported_number_rate(_report(body), CHUNKS) == 0.0


def test_unsupported_number_rate_flags_hallucinated_figures() -> None:
    body = "Revenue reached $416.2 billion, and services revenue was $109.2 billion."
    assert checks.unsupported_number_rate(_report(body), CHUNKS) == 0.5


def test_unsupported_number_rate_ignores_appendix() -> None:
    assert checks.unsupported_number_rate(_report("Revenue was $416.16 billion."), CHUNKS) == 0.0


# --- ticker_accuracy -------------------------------------------------------------------


def test_ticker_accuracy_passes_for_requested_ticker_only() -> None:
    assert checks.ticker_accuracy(_report("Apple (AAPL) grew revenue."), "AAPL") is True


def test_ticker_accuracy_fails_when_another_ticker_is_discussed() -> None:
    assert checks.ticker_accuracy(_report("AAPL grew; Walmart (WMT) slowed."), "AAPL") is False


def test_ticker_accuracy_fails_when_requested_ticker_is_absent() -> None:
    assert checks.ticker_accuracy(_report("The company grew revenue."), "AAPL") is False


# --- disclaimer_present ----------------------------------------------------------------


def test_disclaimer_present_passes() -> None:
    assert checks.disclaimer_present(_report("Body.")) is True


def test_disclaimer_present_fails_when_missing_or_edited() -> None:
    assert checks.disclaimer_present(_report("Body.", disclaimer=False)) is False
    edited = _report("Body.").replace("**not** investment advice", "investment advice")
    assert checks.disclaimer_present(edited) is False


# --- refusal_accuracy ------------------------------------------------------------------


def test_refusal_accuracy_passes_when_no_number_is_stated() -> None:
    body = "Future fiscal 2031 revenue is not disclosed in any filing, so I cannot answer."
    assert checks.refusal_accuracy(_report(body)) is True


def test_refusal_accuracy_fails_when_a_number_is_stated() -> None:
    assert checks.refusal_accuracy(_report("Fiscal 2031 revenue will be $612 billion.")) is False


# --- aggregation -----------------------------------------------------------------------


@pytest.mark.parametrize("must_refuse,expected", [(True, True), (False, None)])
def test_run_checks_scopes_refusal_to_refusal_cases(must_refuse, expected) -> None:
    out = checks.run_checks(
        _report("Apple (AAPL) is discussed."), CHUNKS, ticker="AAPL", must_refuse=must_refuse
    )
    assert out["refusal_accuracy"] is expected
    assert set(out) >= {
        "citation_coverage",
        "unsupported_number_rate",
        "ticker_accuracy",
        "disclaimer_present",
        "refusal_accuracy",
    }
