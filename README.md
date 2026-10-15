# Stock Analyst

[![eval](https://github.com/jaysheeldodia/StockAnalyst-AI/actions/workflows/eval.yml/badge.svg)](https://github.com/jaysheeldodia/StockAnalyst-AI/actions/workflows/eval.yml)

A multi-agent stock research system built with LangGraph and served with FastAPI. It generates a structured analyst-style report using persistent RAG (ChromaDB) and analytics storage (SQLite).

## What it does

- Takes a single input: a stock ticker (for example, `AAPL`).
- Collects data using multiple agents (news, transcripts, financials, sentiment, and macro).
- Normalizes and ranks signals, checks for contradictions, then writes a thesis and final report.
- Adds an audit block and a legal disclaimer to the output.

## Requirements

- Python 3.11+
- A `.env` file (see `./.env.example`)

Optional for full LLM-powered output:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional)
- `TAVILY_API_KEY` if you enable live news/social/financial modes

## Quick start

1. Install dependencies:

```bash
pip install -e .
```

2. Configure environment variables:

```bash
cp .env.example .env
```

If you do not set `OPENAI_API_KEY`, the app will run with mock signals and template text.

3. Seed RAG documents (so retrieval has content to use):

```bash
python -m app.bootstrap
```

4. Start the API server:

```bash
uvicorn app.api.main:app --reload
```

5. Open the UI:

`http://localhost:8000/`

## Run an example (CLI script)

```bash
python examples/run_example.py
```

## Environment variables (common)

- `OPENAI_API_KEY`: enables the full LLM experience
- `OPENAI_MODEL`: defaults to `gpt-4o-mini`
- `NEWS_DATA_MODE`: set to `live` for real-time news (optional)
- `FINANCIAL_DATA_MODE`: set to `live` for real-time financials (optional)
- `SOCIAL_DATA_MODE`: set to `live` for real-time social sentiment (optional)
- `TAVILY_API_KEY`: required for `*_DATA_MODE=live`

## Project layout

- `app/`: application code (agents, LangGraph workflow, API, storage, UI assets)
- `tests/`: automated tests
- `examples/`: runnable scripts
- `data/`: local persistent artifacts (ChromaDB + SQLite). Ignored by git.

## Development

Common commands (see `Makefile`):

- `make dev`: run the API
- `make test`: run tests
- `make lint`: run ruff checks
- `make format`: run ruff formatting
- `make eval`: full golden set (judged layer with `EVAL_JUDGE=1`)
- `make eval-smoke`: 5 cases, no judge, then the regression gate
- `make eval-check`: gate the newest result against `evals/baseline.json`
- `make eval-baseline`: re-measure and overwrite `evals/baseline.json`

## Results

Source: [`evals/baseline.json`](evals/baseline.json), which holds the result files
`dadc27c-20261015T002414.json` (smoke) and `dadc27c-20261015T002417.json` (full). Run
conditions: clean commit `dadc27c`, dataset sha256 `d8d7903c3c12beb5…`, all
`*_DATA_MODE=mock`, replayed market fixtures, Ragas 0.4.3, `top_k=5`, host `Darwin-arm64`,
and **agent LLM off** (`agent_llm_configured: false`, the template report path). The four
judged metrics in this table are `n/a` because this baseline did not run the judge. Judged
numbers from later LLM-on runs are in the Phase 5 table below. Latency is gated only against
a baseline from the same host, so CI needs its own baseline before it gates latency.

| metric | smoke (5 cases) | full (60 cases) |
|---|---|---|
| `citation_coverage` | 0.233 | 0.233 |
| `unsupported_number_rate` | 0.720 | 0.720 |
| `ticker_accuracy` | 1.000 | 1.000 |
| `disclaimer_present` | 1.000 | 1.000 |
| `refusal_accuracy` | n/a | 0.000 |
| `answer_key_recall` | 0.000 | 0.023 |
| `faithfulness` | n/a | n/a |
| `answer_relevancy` | n/a | n/a |
| `context_precision` | n/a | n/a |
| `context_recall` | n/a | n/a |
| `latency_p50` | 0.34s | 0.33s |
| `latency_p95` | 0.63s | 0.59s |
| `latency_p99` | 0.69s | 0.64s |
| `mean_usd_per_report` | $0.000000 | $0.000000 |
| `mean_tokens_per_report` | 0 | 0 |
| `failure_rate` | 0.000 | 0.000 |

The harness, metric definitions, and gate thresholds live in [`evals/`](evals). The
golden set schema is in [`evals/golden/README.md`](evals/golden/README.md).

## Phase 5

Dataset frozen at sha256 `d8d7903c3c12beb5c6810d7b3f48f7e88e2476e5858fa0570091b56221a6cb7e`
([`evals/phase5/dataset.sha256`](evals/phase5/dataset.sha256), matches
`evals/golden/stock_qa.jsonl`). One change: `RetrievalConfig.top_k` 5 → 8 in
[`app/config.py`](app/config.py). Two judged full runs at each setting, agent LLM on,
`EVAL_JUDGE=1`, mock data modes, replayed market fixtures.

Sources: [`evals/phase5/before.json`](evals/phase5/before.json),
[`before-repeat.json`](evals/phase5/before-repeat.json),
[`after.json`](evals/phase5/after.json),
[`after-repeat.json`](evals/phase5/after-repeat.json).

| metric | k5-1 | k5-2 | k8-1 | k8-2 |
|---|---|---|---|---|
| `citation_coverage` | 0.540 | 0.506 | 0.506 | 0.580 |
| `unsupported_number_rate` | 0.070 | 0.065 | 0.123 | 0.067 |
| `ticker_accuracy` | 1.000 | 1.000 | 1.000 | 1.000 |
| `disclaimer_present` | 1.000 | 1.000 | 1.000 | 1.000 |
| `refusal_accuracy` | 0.000 | 0.000 | 0.000 | 0.000 |
| `answer_key_recall` | 0.403 | 0.393 | 0.393 | 0.313 |
| `faithfulness` | 0.602 | 0.487 | 0.450 | 0.410 |
| `answer_relevancy` | 0.283 | 0.420 | 0.511 | 0.473 |
| `context_precision` | 0.380 | 0.380 | 0.378 | 0.378 |
| `context_recall` | 0.980 | 0.980 | 1.000 | 1.000 |
| `latency_p50` | 21.31s | 19.60s | 21.73s | 18.47s |
| `latency_p95` | 36.15s | 24.81s | 23.34s | 24.42s |
| `latency_p99` | 38.65s | 25.82s | 23.59s | 24.70s |
| `mean_usd_per_report` | $0.004370 | $0.003917 | $0.004609 | $0.004147 |
| `mean_tokens_per_report` | 14584 | 13190 | 16355 | 14742 |
| `failure_rate` | 0.000 | 0.000 | 0.000 | 0.000 |

`context_recall` moved 0.980 → 1.000 on both after runs. No other quality metric moved
outside the `top_k=5` repeat envelope in both after runs (`unsupported_number_rate` 0.123 on
k8-1 was not repeated; k8-2 was 0.067). `faithfulness` is too noisy between identical
`top_k=5` runs (0.602 vs 0.487) to attribute a change to `top_k`. The 5 → 8 change was
reverted. `top_k` in `app/config.py` is 5.

### Reproduce

```bash
pip install -e ".[dev]"
OPENAI_API_KEY= make eval
make eval-check
```
