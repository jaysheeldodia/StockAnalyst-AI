"""Regression gate: compare a result file with evals/baseline.json.

  python -m evals.compare_baseline                    # newest result vs its profile's baseline
  python -m evals.compare_baseline --result FILE
  python -m evals.compare_baseline --update-baseline  # newest smoke + full results -> baseline

Exit codes: 0 pass, 1 regression or case exception, 2 cannot compare.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evals.lib.report import DETERMINISTIC, JUDGED

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "evals" / "results"
BASELINE = ROOT / "evals" / "baseline.json"

FAITHFULNESS_MAX_DROP_PTS = 3.0
UNSUPPORTED_MAX_RISE_PTS = 2.0
P95_MAX_RISE_PCT = 20.0
COST_MAX_RISE_PCT = 20.0


def newest_result(profile: str | None = None) -> Path | None:
    files = sorted(RESULTS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        if profile is None:
            return path
        if json.loads(path.read_text(encoding="utf-8"))["meta"]["profile"] == profile:
            return path
    return None


def _pct_change(base: float, cur: float) -> float:
    if base == 0:
        return 0.0 if cur == 0 else float("inf")
    return (cur / base - 1.0) * 100.0


def _fmt(v: float | None, digits: int = 3) -> str:
    return "n/a" if v is None else f"{v:.{digits}f}"


def compare(
    result: dict[str, Any], baseline: dict[str, Any], *, same_host: bool = True
) -> tuple[list[tuple], bool]:
    """Return (rows, failed). Each row: metric, baseline, current, delta, rule, status.

    Latency is only gated when result and baseline ran on the same host label.
    """
    rows: list[tuple] = []
    failed = False
    cur_s, base_s = result["summary"], baseline["summary"]

    for name in DETERMINISTIC + JUDGED:
        b = base_s["metrics"][name]["value"]
        c = cur_s["metrics"][name]["value"]
        rule, status = "info", "info"
        if name == "faithfulness":
            rule = f"drop <= {FAITHFULNESS_MAX_DROP_PTS:g} pts"
        if name == "unsupported_number_rate":
            rule = f"rise <= {UNSUPPORTED_MAX_RISE_PTS:g} pts"
        if b is None or c is None:
            delta = "n/a"
            status = "n/a"
        else:
            d = (c - b) * 100.0
            delta = f"{d:+.2f} pts"
            if name == "faithfulness":
                status = "FAIL" if d < -FAITHFULNESS_MAX_DROP_PTS else "PASS"
            elif name == "unsupported_number_rate":
                status = "FAIL" if d > UNSUPPORTED_MAX_RISE_PTS else "PASS"
        failed |= status == "FAIL"
        rows.append((name, _fmt(b), _fmt(c), delta, rule, status))

    for q in ("p50", "p95", "p99"):
        b, c = base_s["latency_s"][q], cur_s["latency_s"][q]
        rule = f"rise <= {P95_MAX_RISE_PCT:g}%" if q == "p95" else "info"
        if b is None or c is None:
            delta, status = "n/a", "n/a"
        else:
            d = _pct_change(b, c)
            delta = f"{d:+.1f}%"
            status = ("FAIL" if d > P95_MAX_RISE_PCT else "PASS") if q == "p95" else "info"
            if q == "p95" and not same_host:
                rule, status = "not gated: different host", "n/a"
        failed |= status == "FAIL"
        rows.append((f"latency_{q}_s", _fmt(b, 2), _fmt(c, 2), delta, rule, status))

    for key, gated in (("mean_usd_per_report", True), ("mean_tokens_per_report", False)):
        b, c = base_s[key]["value"], cur_s[key]["value"]
        rule = f"rise <= {COST_MAX_RISE_PCT:g}%" if gated else "info"
        if b is None or c is None:
            delta, status = "n/a", "n/a"
        else:
            d = _pct_change(b, c)
            delta = f"{d:+.1f}%"
            status = ("FAIL" if d > COST_MAX_RISE_PCT else "PASS") if gated else "info"
        failed |= status == "FAIL"
        digits = 6 if gated else 0
        rows.append((key, _fmt(b, digits), _fmt(c, digits), delta, rule, status))

    bf, cf = base_s["failure_rate"], cur_s["failure_rate"]
    status = "FAIL" if cf["failures"] else "PASS"
    failed |= status == "FAIL"
    rows.append((
        "case_exceptions",
        f"{bf['failures']}/{bf['n']}",
        f"{cf['failures']}/{cf['n']}",
        f"{cf['failures'] - bf['failures']:+d}",
        "must be 0",
        status,
    ))
    return rows, failed


def format_rows(rows: list[tuple]) -> str:
    header = ("metric", "baseline", "current", "delta", "rule", "status")
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]

    def line(r):
        return "| " + " | ".join(str(c).ljust(w) for c, w in zip(r, widths)) + " |"

    return "\n".join([line(header), "|" + "|".join("-" * (w + 2) for w in widths) + "|", *map(line, rows)])


def _snapshot(result: dict[str, Any], source: Path) -> dict[str, Any]:
    return {"source_file": source.name, "meta": result["meta"], "summary": result["summary"]}


def update_baseline() -> int:
    profiles: dict[str, Any] = {}
    for profile in ("smoke", "full"):
        path = newest_result(profile)
        if path is None:
            print(f"no {profile} result in {RESULTS}; run it first", file=sys.stderr)
            return 2
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["summary"]["failure_rate"]["failures"]:
            print(f"refusing to baseline {path.name}: it has case exceptions", file=sys.stderr)
            return 2
        profiles[profile] = _snapshot(result, path)
        print(f"{profile}: {path.name}")
    BASELINE.write_text(json.dumps({"schema": 1, "profiles": profiles}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {BASELINE.relative_to(ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--profile", choices=("smoke", "full"))
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)

    if args.update_baseline:
        return update_baseline()

    path = args.result or newest_result(args.profile)
    if path is None or not path.exists():
        print(f"no result file found in {RESULTS}", file=sys.stderr)
        return 2
    if not args.baseline.exists():
        print(f"no baseline at {args.baseline}; run make eval-baseline", file=sys.stderr)
        return 2
    result = json.loads(path.read_text(encoding="utf-8"))
    profile = result["meta"]["profile"]
    base = json.loads(args.baseline.read_text(encoding="utf-8"))["profiles"].get(profile)
    if base is None:
        print(f"baseline has no '{profile}' profile", file=sys.stderr)
        return 2

    print(f"result:   {path.name} (profile={profile}, sha={result['meta']['git_sha']})")
    print(f"baseline: {base['source_file']} (sha={base['meta']['git_sha']})")
    if result["meta"]["judge_enabled"] != base["meta"]["judge_enabled"]:
        print("note: judge enabled differs from baseline; judged metrics compare as n/a")
    for key in ("dataset_sha256", "agent_llm_configured", "model"):
        if result["meta"].get(key) != base["meta"].get(key):
            print(
                f"cannot compare: {key} differs (baseline={base['meta'].get(key)!r}, "
                f"result={result['meta'].get(key)!r}); re-run make eval-baseline",
                file=sys.stderr,
            )
            return 2

    result_host, base_host = result["meta"].get("host"), base["meta"].get("host")
    same_host = result_host == base_host
    if not same_host:
        print(f"note: host differs (baseline={base_host!r}, result={result_host!r}); latency not gated")
    rows, failed = compare(result, base, same_host=same_host)
    print(format_rows(rows))
    print("\nGATE: FAIL" if failed else "\nGATE: PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
