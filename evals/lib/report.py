"""Aggregate per-case rows into metrics, print a table, and write the result JSON."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np

DETERMINISTIC = [
    "citation_coverage",
    "unsupported_number_rate",
    "ticker_accuracy",
    "disclaimer_present",
    "refusal_accuracy",
    "answer_key_recall",
]
JUDGED = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


def _metric(values: list[Any], reason_if_empty: str) -> dict[str, Any]:
    present = [float(v) for v in values if v is not None]
    if not present:
        return {"value": None, "n": 0, "reason": reason_if_empty}
    return {"value": mean(present), "n": len(present), "reason": None}


def aggregate(cases: list[dict], analyses: list[dict], *, judge_enabled: bool) -> dict[str, Any]:
    ok = [c for c in cases if not c.get("error")]
    metrics: dict[str, Any] = {}
    for name in DETERMINISTIC:
        reason = "no case produced a value"
        if name == "refusal_accuracy" and not any(c["must_refuse"] for c in ok):
            reason = "no must_refuse case in this run"
        if name in ("citation_coverage", "unsupported_number_rate"):
            reason = "no report stated a claim or number"
        metrics[name] = _metric([c.get(name) for c in ok], reason)
    for name in JUDGED:
        reason = "judge disabled (set EVAL_JUDGE=1)" if not judge_enabled else "judge returned no value"
        metrics[name] = _metric([c.get(name) for c in ok], reason)

    finished = [a for a in analyses if not a.get("error")]
    latencies = [a["latency_s"] for a in finished]
    if latencies:
        p50, p95, p99 = (float(np.percentile(latencies, q)) for q in (50, 95, 99))
        latency = {"p50": p50, "p95": p95, "p99": p99, "n": len(latencies), "reason": None}
    else:
        latency = {"p50": None, "p95": None, "p99": None, "n": 0, "reason": "no analysis finished"}

    costs = [a["cost_usd"] for a in finished]
    if finished and any(c is None for c in costs):
        cost = {"value": None, "n": len(costs), "reason": "a model in the run has no price in pricing.py"}
    else:
        cost = _metric(costs, "no analysis finished")
    tokens = _metric([a["total_tokens"] for a in finished], "no analysis finished")

    judge_costs = [c.get("judge_cost_usd") for c in cases if c.get("judge_cost_usd") is not None]
    attempted = [c for c in cases if not c.get("skipped")]
    failures = [c for c in attempted if c.get("error") or c.get("judge_error")]
    return {
        "metrics": metrics,
        "latency_s": latency,
        "mean_usd_per_report": cost,
        "mean_tokens_per_report": tokens,
        "judge_total_usd": sum(judge_costs) if judge_enabled else 0.0,
        "failure_rate": {
            "value": len(failures) / len(attempted) if attempted else None,
            "n": len(attempted),
            "failures": len(failures),
            "reason": None if attempted else "no case attempted",
        },
        "cases_skipped": sum(1 for c in cases if c.get("skipped")),
    }


def _fmt(v: Any, kind: str = "ratio") -> str:
    if v is None:
        return "n/a"
    if kind == "usd":
        return f"${v:.6f}"
    if kind == "s":
        return f"{v:.2f}s"
    if kind == "int":
        return f"{v:.0f}"
    return f"{v:.3f}"


def format_table(result: dict[str, Any]) -> str:
    s = result["summary"]
    rows: list[tuple[str, str, str, str]] = []
    for name in DETERMINISTIC + JUDGED:
        m = s["metrics"][name]
        layer = "deterministic" if name in DETERMINISTIC else "judged"
        rows.append((name, layer, _fmt(m["value"]), str(m["n"]) if m["value"] is not None else m["reason"]))
    lat = s["latency_s"]
    for q in ("p50", "p95", "p99"):
        rows.append((f"latency_{q}", "ops", _fmt(lat[q], "s"), str(lat["n"]) if lat[q] is not None else lat["reason"]))
    for key, kind in (("mean_usd_per_report", "usd"), ("mean_tokens_per_report", "int")):
        m = s[key]
        rows.append((key, "ops", _fmt(m["value"], kind), str(m["n"]) if m["value"] is not None else m["reason"]))
    rows.append(("judge_total_usd", "ops", _fmt(s["judge_total_usd"], "usd"), ""))
    fr = s["failure_rate"]
    rows.append(("failure_rate", "ops", _fmt(fr["value"]), f"{fr['failures']}/{fr['n']}"))

    widths = [max(len(r[i]) for r in rows + [("metric", "layer", "value", "n / note")]) for i in range(4)]
    header = ("metric", "layer", "value", "n / note")

    def line(r):
        return "| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |"

    out = [line(header), "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    out.extend(line(r) for r in rows)
    return "\n".join(out)


def _summary_rows(summary: dict[str, Any]) -> list[tuple[str, str]]:
    rows = [(name, _fmt(summary["metrics"][name]["value"])) for name in DETERMINISTIC + JUDGED]
    rows += [(f"latency_{q}", _fmt(summary["latency_s"][q], "s")) for q in ("p50", "p95", "p99")]
    rows.append(("mean_usd_per_report", _fmt(summary["mean_usd_per_report"]["value"], "usd")))
    rows.append(("mean_tokens_per_report", _fmt(summary["mean_tokens_per_report"]["value"], "int")))
    rows.append(("failure_rate", _fmt(summary["failure_rate"]["value"])))
    return rows


def markdown_table(columns: dict[str, dict[str, Any]]) -> str:
    """Markdown table with one value column per summary (e.g. before / after)."""
    per_col = {label: dict(_summary_rows(s)) for label, s in columns.items()}
    names = [name for name, _ in _summary_rows(next(iter(columns.values())))]
    out = ["| metric | " + " | ".join(columns) + " |", "|---" * (len(columns) + 1) + "|"]
    out += [f"| `{n}` | " + " | ".join(per_col[c][n] for c in columns) + " |" for n in names]
    return "\n".join(out)


def _load_summary(spec: str) -> tuple[str, dict[str, Any]]:
    """spec is LABEL=PATH or LABEL=PATH#profile (for baseline.json)."""
    label, _, target = spec.partition("=")
    path, _, profile = target.partition("#")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if profile:
        data = data["profiles"][profile]
    return label, data["summary"]


if __name__ == "__main__":
    import sys

    print(markdown_table(dict(_load_summary(s) for s in sys.argv[1:])))


def write_result(result: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = result["meta"]
    stamp = meta["started_at_utc"].replace(":", "").replace("-", "").split(".")[0]
    path = out_dir / f"{meta['git_sha']}-{stamp}.json"
    path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    return path
