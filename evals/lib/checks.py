"""Deterministic report checks. No LLM, no network, no cost."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

from app.legal.disclaimer import RESEARCH_DISCLAIMER

APPENDIX_MARKER = "## Market snapshot (third-party data)"

TICKER_ALIASES: dict[str, list[str]] = {
    "AAPL": ["Apple"],
    "JPM": ["JPMorgan", "JP Morgan"],
    "XOM": ["Exxon", "ExxonMobil"],
    "JNJ": ["Johnson & Johnson", "J&J"],
    "WMT": ["Walmart", "Wal-Mart"],
}

# Claims sharing at least this fraction of content words with one chunk count as cited.
WORD_OVERLAP_THRESHOLD = 0.5

_SCALES = {
    "trillion": 1e12, "tn": 1e12, "T": 1e12,
    "billion": 1e9, "bn": 1e9, "B": 1e9,
    "million": 1e6, "M": 1e6,
    "thousand": 1e3, "K": 1e3,
}
_NUM_RE = re.compile(
    r"(?<![\w.$])(?P<sign>[-+\u2212])?(?P<cur>\$)?"
    r"(?P<int>\d{1,3}(?:,\d{3})+|\d+)(?P<frac>\.\d+)?"
    r"(?:\s?(?P<word>%|percent\b|trillion\b|billion\b|million\b|thousand\b|bn\b|tn\b)"
    r"|(?P<letter>[TBMK])\b)?"
)
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+(?:Z|[+-]\d{2}:?\d{2})?)?")
_LIST_MARKER_RE = re.compile(r"^\s*\d+[.)]\s", re.M)
_METRIC_RE = re.compile(
    r"\b(revenue|sales|margin|income|profit|earnings|eps|cash flow|debt|liabilit\w*|equity|"
    r"price|target|p/e|valuation|beta|growth|dividend|buyback|guidance)\b",
    re.I,
)
_WORD_RE = re.compile(r"[a-z][a-z'&-]{3,}")
_STOPWORDS = {
    "with", "that", "this", "from", "have", "were", "been", "which", "their", "there", "about",
    "into", "over", "than", "also", "while", "remain", "remains", "versus", "compared", "year",
    "fiscal", "company", "stock", "shares", "could", "would", "should", "within", "across",
}


@dataclass(frozen=True, slots=True)
class Number:
    text: str
    value: float
    mantissa: float
    decimals: int
    scale: float
    is_pct: bool


def extract_numbers(text: str) -> list[Number]:
    """Numbers stated in text, excluding years, dates, list markers, and labels like 10-K."""
    text = _LIST_MARKER_RE.sub(" ", _DATE_RE.sub(" ", text))
    out: list[Number] = []
    for m in _NUM_RE.finditer(text):
        unit = m.group("word") or m.group("letter")
        tail = text[m.end() : m.end() + 2]
        if not unit and (tail[:1].isalpha() or (tail[:1] == "-" and tail[1:2].isalpha())):
            continue
        int_part, frac = m.group("int"), m.group("frac") or ""
        mantissa = float(int_part.replace(",", "") + frac)
        if (
            not unit
            and not m.group("cur")
            and not frac
            and "," not in int_part
            and 1900 <= mantissa <= 2100
        ):
            continue
        is_pct = unit in ("%", "percent")
        scale = 1.0 if (unit is None or is_pct) else _SCALES[unit]
        sign = -1.0 if m.group("sign") in ("-", "\u2212") else 1.0
        out.append(
            Number(
                text=m.group(0).strip(),
                value=sign * mantissa * scale,
                mantissa=mantissa,
                decimals=max(len(frac) - 1, 0),
                scale=scale,
                is_pct=is_pct,
            )
        )
    return out


def _fits(x: Number, y: Number) -> bool:
    """Does x, shown at y's unit and precision, read as y?"""
    candidates = [abs(x.value)]
    if y.is_pct and not x.is_pct:
        candidates.append(abs(x.value) * 100.0)
    if x.is_pct and not y.is_pct:
        candidates.append(abs(x.value) / 100.0)
    target = round(y.mantissa, y.decimals)
    return any(
        math.isclose(round(c / y.scale, y.decimals), target, abs_tol=1e-9) for c in candidates
    )


def numbers_match(a: Number, b: Number) -> bool:
    return _fits(a, b) or _fits(b, a)


def narrative_body(report: str) -> str:
    body = report.split(APPENDIX_MARKER, 1)[0]
    return body.replace(RESEARCH_DISCLAIMER, "")


def market_snapshot_text(snapshot: dict[str, Any] | None) -> str:
    ms = snapshot or {}
    return json.dumps({"quote": ms.get("quote") or {}, "metrics": ms.get("metrics") or {}})


def _claims(body: str) -> list[str]:
    units: list[str] = []
    in_code = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s or s.startswith(("#", "|", "---")):
            continue
        s = re.sub(r"^([-*+]|\d+[.)])\s+", "", s)
        units.extend(p for p in re.split(r"(?<=[.!?])\s+", s) if p.strip())
    return [u for u in units if extract_numbers(u) or _METRIC_RE.search(u)]


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def _supported(n: Number, evidence: list[Number]) -> bool:
    return any(numbers_match(n, e) for e in evidence)


def citation_coverage(report: str, evidence_texts: list[str]) -> float | None:
    """Share of factual claims backed by a retrieved chunk (shared number or word overlap)."""
    claims = _claims(narrative_body(report))
    if not claims:
        return None
    evidence_nums = [n for t in evidence_texts for n in extract_numbers(t)]
    chunk_words = [_content_words(t) for t in evidence_texts]
    cited = 0
    for claim in claims:
        if any(_supported(n, evidence_nums) for n in extract_numbers(claim)):
            cited += 1
            continue
        words = _content_words(claim)
        if words and any(
            len(words & cw) / len(words) >= WORD_OVERLAP_THRESHOLD for cw in chunk_words
        ):
            cited += 1
    return cited / len(claims)


def unsupported_number_rate(report: str, evidence_texts: list[str]) -> float | None:
    """Share of numbers in the narrative that appear in no evidence text."""
    nums = extract_numbers(narrative_body(report))
    if not nums:
        return None
    evidence_nums = [n for t in evidence_texts for n in extract_numbers(t)]
    return sum(not _supported(n, evidence_nums) for n in nums) / len(nums)


def _mentions(text: str, ticker: str) -> bool:
    names = [ticker, *TICKER_ALIASES.get(ticker, [])]
    return any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text) for n in names)


def ticker_accuracy(report: str, ticker: str) -> bool:
    """The narrative names the requested ticker and no other ticker in the universe."""
    body = narrative_body(report)
    others = [t for t in TICKER_ALIASES if t != ticker]
    return _mentions(body, ticker) and not any(_mentions(body, t) for t in others)


def disclaimer_present(report: str) -> bool:
    norm = " ".join(report.split())
    return " ".join(RESEARCH_DISCLAIMER.split()) in norm


def refusal_accuracy(report: str) -> bool:
    """For unanswerable cases: the narrative states no number."""
    return not extract_numbers(narrative_body(report))


def _answer_key_number(key: str, value: float) -> Number:
    if key.endswith("_usd_bn"):
        scale, is_pct = 1e9, False
    elif key.endswith("_pct"):
        scale, is_pct = 1.0, True
    else:
        scale, is_pct = 1.0, False
    text = f"{value}"
    decimals = len(text.split(".")[1]) if "." in text else 0
    return Number(text, abs(value) * scale, abs(value), decimals, scale, is_pct)


def answer_key_recall(report: str, answer_key: dict[str, float] | None) -> float | None:
    """Share of answer-key figures that the narrative states (informational, not gated)."""
    if not answer_key:
        return None
    nums = extract_numbers(narrative_body(report))
    keys = [_answer_key_number(k, v) for k, v in answer_key.items()]
    return sum(any(numbers_match(k, n) for n in nums) for k in keys) / len(keys)


def run_checks(
    report: str,
    evidence_texts: list[str],
    *,
    ticker: str,
    must_refuse: bool,
    answer_key: dict[str, float] | None = None,
) -> dict[str, Any]:
    return {
        "citation_coverage": citation_coverage(report, evidence_texts),
        "unsupported_number_rate": unsupported_number_rate(report, evidence_texts),
        "ticker_accuracy": ticker_accuracy(report, ticker),
        "disclaimer_present": disclaimer_present(report),
        "refusal_accuracy": refusal_accuracy(report) if must_refuse else None,
        "answer_key_recall": answer_key_recall(report, answer_key),
    }
