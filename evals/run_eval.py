"""Run the evaluation harness.

  python -m evals.run_eval --profile full     # all cases; judge when EVAL_JUDGE=1
  python -m evals.run_eval --profile smoke    # 5 cases, agent LLM off, no judge

Env: EVAL_JUDGE=1, EVAL_MAX_CASES=N, EVAL_MAX_USD=X, *_DATA_MODE (default mock).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "evals" / "golden" / "stock_qa.jsonl"
CORPUS = ROOT / "evals" / "corpus" / "stock_corpus.jsonl"
FIXTURES = ROOT / "evals" / "fixtures" / "market"
CACHE = ROOT / "evals" / ".cache"
RESULTS = ROOT / "evals" / "results"
DATA_MODES = ("NEWS_DATA_MODE", "FINANCIAL_DATA_MODE", "SOCIAL_DATA_MODE")
SMOKE_CASES = 5

logger = logging.getLogger("evals")


def _prepare_env(profile: str) -> None:
    """Must run before any app import: app.config loads .env without overriding set vars."""
    for key in DATA_MODES:
        os.environ.setdefault(key, "mock")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
    if profile == "smoke":
        os.environ["OPENAI_API_KEY"] = ""


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_rows(path: Path = GOLDEN) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def dataset_sha256(path: Path = GOLDEN) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_rows(rows: list[dict], profile: str, max_cases: int | None) -> list[dict]:
    if profile == "smoke":
        picked: dict[str, dict] = {}
        for r in rows:
            if not r["must_refuse"] and r["ticker"] not in picked:
                picked[r["ticker"]] = r
        rows = list(picked.values())[:SMOKE_CASES]
    if max_cases is not None:
        rows = rows[:max_cases]
    return rows


def _prior_costs(profile: str) -> tuple[float | None, float | None, str | None]:
    """Measured (usd per analysis, usd per judged case, file) from the newest same-profile run."""
    if not RESULTS.exists():
        return None, None, None
    for path in sorted(RESULTS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            res = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if res.get("meta", {}).get("profile") != profile:
            continue
        s = res["summary"]
        per_analysis = s["mean_usd_per_report"]["value"]
        per_judge = s.get("judge_usd_per_case")
        return per_analysis, per_judge, path.name
    return None, None, None


class Budget:
    def __init__(self, max_usd: float | None, est_analysis: float | None, est_judge: float | None):
        self.max_usd = max_usd
        self.spent = 0.0
        self.analysis_costs: list[float] = []
        self.judge_costs: list[float] = []
        self.est_analysis = est_analysis
        self.est_judge = est_judge

    def _next(self, observed: list[float], prior: float | None) -> float:
        if observed:
            return sum(observed) / len(observed)
        return prior or 0.0

    def allows(self, kind: str) -> bool:
        if self.max_usd is None:
            return True
        nxt = (
            self._next(self.analysis_costs, self.est_analysis)
            if kind == "analysis"
            else self._next(self.judge_costs, self.est_judge)
        )
        return self.spent + nxt <= self.max_usd

    def add(self, kind: str, usd: float | None) -> None:
        if usd is None:
            return
        self.spent += usd
        (self.analysis_costs if kind == "analysis" else self.judge_costs).append(usd)


async def run(profile: str, max_cases: int | None, max_usd: float | None) -> dict[str, Any]:
    from langchain_core.callbacks import get_usage_metadata_callback

    import app.graph.market_snapshot as market_snapshot_node
    from app.api.schemas import retrieval_from_raw_results
    from app.config import get_config
    from evals.lib import checks
    from evals.lib.judge import judge_case, make_judge
    from evals.lib.pricing import PRICING_ACCESSED, PRICING_SOURCE, cost_usd
    from evals.lib.report import aggregate

    judge_enabled = profile == "full" and os.getenv("EVAL_JUDGE") == "1"
    started = datetime.now(timezone.utc)
    cfg = get_config()

    # Isolated stores so eval runs never touch data/ and always start from the same corpus.
    shutil.rmtree(CACHE, ignore_errors=True)
    CACHE.mkdir(parents=True)
    cfg.chroma_dir = CACHE / "chroma"
    cfg.sqlite_path = CACHE / "eval.db"
    cfg.chroma_dir.mkdir(parents=True)

    from app.storage.chroma_store import ChromaStore

    corpus = [json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line]
    ChromaStore().upsert_documents(corpus)

    async def _fixture_snapshot(ticker: str) -> dict:
        path = FIXTURES / f"{ticker.upper()}.json"
        if not path.exists():
            raise FileNotFoundError(f"no market fixture for {ticker}: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    market_snapshot_node.fetch_market_snapshot_async = _fixture_snapshot

    from app.services.analysis_service import AnalysisService

    service = AnalysisService()

    rows = select_rows(load_rows(), profile, max_cases)
    est_analysis, est_judge, est_file = _prior_costs(profile)
    groups: OrderedDict[tuple[str, str], list[dict]] = OrderedDict()
    for r in rows:
        groups.setdefault((r["ticker"], r["horizon"]), []).append(r)
    n_judged = sum(1 for r in rows if not r["must_refuse"]) if judge_enabled else 0
    if est_file and est_analysis is not None:
        estimate = len(groups) * est_analysis + n_judged * (est_judge or 0.0)
        judge_note = "" if (est_judge is not None or not n_judged) else " (judge cost unknown)"
        print(f"Estimated cost: ${estimate:.4f}{judge_note} from measured run {est_file}")
    else:
        print("Estimated cost: n/a (no prior measured run of this profile)")
    print(
        f"Profile={profile} cases={len(rows)} analyses={len(groups)} judge={judge_enabled} "
        f"cap={'none' if max_usd is None else f'${max_usd:.2f}'}"
    )

    budget = Budget(max_usd, est_analysis, est_judge)
    judge = make_judge() if judge_enabled else None
    analyses: list[dict] = []
    cases: list[dict] = []

    for (ticker, horizon), group in groups.items():
        if not budget.allows("analysis"):
            for r in group:
                cases.append({"id": r["id"], "ticker": ticker, "must_refuse": r["must_refuse"],
                              "skipped": "EVAL_MAX_USD cap reached"})
            continue
        analysis: dict[str, Any] = {"ticker": ticker, "horizon": horizon, "error": None}
        state: dict | None = None
        with get_usage_metadata_callback() as usage_cb:
            t0 = time.perf_counter()
            try:
                state = await service.analyze(ticker, horizon=horizon)
            except Exception as exc:
                analysis["error"] = f"{type(exc).__name__}: {exc}"
                analysis["traceback"] = traceback.format_exc()
                logger.error("analysis failed for %s: %s", ticker, analysis["error"])
            analysis["latency_s"] = time.perf_counter() - t0
            usage = dict(usage_cb.usage_metadata)

        in_tok = sum(u.get("input_tokens", 0) for u in usage.values())
        out_tok = sum(u.get("output_tokens", 0) for u in usage.values())
        per_model = [cost_usd(m, u.get("input_tokens", 0), u.get("output_tokens", 0)) for m, u in usage.items()]
        analysis.update(
            usage_by_model=usage,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            cost_usd=None if any(c is None for c in per_model) else sum(per_model),
        )
        budget.add("analysis", analysis["cost_usd"])

        chunks = retrieval_from_raw_results(state["raw_results"]) if state else []
        report = state["report"] if state else ""
        analysis["report"] = report
        analysis["retrieved_chunk_ids"] = [c.chunk_id for c in chunks]
        analyses.append(analysis)

        contexts = [c.text for c in chunks]
        evidence = contexts + ([checks.market_snapshot_text(state.get("market_snapshot"))] if state else [])

        for r in group:
            case: dict[str, Any] = {
                "id": r["id"], "ticker": ticker, "type": r["type"], "must_refuse": r["must_refuse"],
                "error": analysis["error"],
            }
            if not analysis["error"]:
                case.update(
                    checks.run_checks(
                        report, evidence, ticker=ticker, must_refuse=r["must_refuse"],
                        answer_key=r["answer_key"],
                    )
                )
            if judge is not None and not analysis["error"] and not r["must_refuse"]:
                if budget.allows("judge"):
                    judged = await asyncio.to_thread(
                        judge_case,
                        question=r["question"],
                        answer=checks.narrative_body(report),
                        contexts=contexts,
                        reference=r["reference"],
                        judge=judge,
                    )
                    case.update(judged)
                    budget.add("judge", judged["judge_cost_usd"])
                else:
                    case["judge_skipped"] = "EVAL_MAX_USD cap reached"
            cases.append(case)

    summary = aggregate(cases, analyses, judge_enabled=judge_enabled)
    judged_costs = [c["judge_cost_usd"] for c in cases if c.get("judge_cost_usd") is not None]
    summary["judge_usd_per_case"] = sum(judged_costs) / len(judged_costs) if judged_costs else None
    summary["total_usd"] = budget.spent

    import ragas

    meta = {
        "profile": profile,
        "git_sha": _git("rev-parse", "--short", "HEAD"),
        "git_dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        "started_at_utc": started.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(GOLDEN.relative_to(ROOT)),
        "dataset_sha256": dataset_sha256(),
        "model": cfg.openai_model,
        "agent_llm_configured": bool(cfg.openai_api_key),
        "judge_enabled": judge_enabled,
        "judge_model": getattr(judge, "model", None),
        "judge_embedding_model": getattr(judge, "embedding_model", None),
        "judge_embedding_cost": "not counted (embedding tokens are not reported by Ragas)",
        "ragas_version": ragas.__version__,
        "data_modes": {k.lower(): os.environ.get(k) for k in DATA_MODES},
        "market_data": "replayed fixtures (evals/fixtures/market)",
        "retrieval": cfg.retrieval.model_dump(),
        "pricing_source": f"{PRICING_SOURCE} (accessed {PRICING_ACCESSED})",
        "max_cases": max_cases,
        "max_usd": max_usd,
        "python": platform.python_version(),
    }
    return {"meta": meta, "summary": summary, "analyses": analyses, "cases": cases}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--profile", choices=("full", "smoke"), default="full")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--out-dir", type=Path, default=RESULTS)
    args = parser.parse_args(argv)

    _prepare_env(args.profile)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    env_cases = os.getenv("EVAL_MAX_CASES")
    max_cases = args.max_cases if args.max_cases is not None else (int(env_cases) if env_cases else None)
    env_usd = os.getenv("EVAL_MAX_USD")
    max_usd = float(env_usd) if env_usd else None

    from evals.lib.report import format_table, write_result

    result = asyncio.run(run(args.profile, max_cases, max_usd))
    path = write_result(result, args.out_dir)
    print()
    print(format_table(result))
    s = result["summary"]
    print(f"\ntotal_usd=${s['total_usd']:.6f}  skipped={s['cases_skipped']}")
    print(f"result: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    failures = s["failure_rate"]["failures"]
    if failures:
        print(f"FAIL: {failures} case(s) raised an exception", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
