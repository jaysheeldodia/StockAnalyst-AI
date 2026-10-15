from __future__ import annotations

import json
from pathlib import Path

import pytest

GOLDEN = Path(__file__).resolve().parent.parent / "evals" / "golden" / "stock_qa.jsonl"
FIELDS = {
    "id",
    "ticker",
    "horizon",
    "type",
    "question",
    "answer_key",
    "claims_required",
    "reference",
    "source",
    "must_refuse",
}
TYPES = {"revenue", "margin", "risk", "comparison", "outlook"}


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line]


def test_row_count_and_split(rows) -> None:
    assert len(rows) == 60
    assert sum(not r["must_refuse"] for r in rows) == 50
    assert sum(r["must_refuse"] for r in rows) == 10


def test_field_names(rows) -> None:
    for r in rows:
        assert set(r) == FIELDS, r["id"]


def test_ids_unique(rows) -> None:
    assert len({r["id"] for r in rows}) == len(rows)


def test_coverage(rows) -> None:
    assert len({r["ticker"] for r in rows}) >= 4
    assert {r["type"] for r in rows} == TYPES


def test_row_values(rows) -> None:
    for r in rows:
        assert isinstance(r["question"], str) and r["question"].strip()
        assert isinstance(r["reference"], str) and r["reference"].strip()
        assert r["source"]["url"].startswith("https://")
        assert len(r["source"]["accessed"]) == 10
        assert isinstance(r["claims_required"], list)
        if r["must_refuse"]:
            assert r["answer_key"] is None
            assert r["claims_required"] == []
        else:
            assert r["answer_key"]
            assert all(isinstance(v, (int, float)) for v in r["answer_key"].values())
            assert r["claims_required"]
