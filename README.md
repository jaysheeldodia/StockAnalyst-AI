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
`63f35dc-20261015T000634.json` (smoke) and `63f35dc-20261015T000638.json` (full). Run
conditions: commit `63f35dc`, dataset sha256 `d8d7903c3c12beb5…`, all `*_DATA_MODE=mock`,
replayed market fixtures, Ragas 0.4.3, `top_k=5`, and **agent LLM off**
(`agent_llm_configured: false`, the template report path). The judged layer has not run
yet, so its four metrics read `n/a`.

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
| `latency_p50` | 0.33s | 0.31s |
| `latency_p95` | 0.61s | 0.61s |
| `latency_p99` | 0.66s | 0.66s |
| `mean_usd_per_report` | $0.000000 | $0.000000 |
| `mean_tokens_per_report` | 0 | 0 |
| `failure_rate` | 0.000 | 0.000 |

The harness, metric definitions, and gate thresholds live in [`evals/`](evals). The
golden set schema is in [`evals/golden/README.md`](evals/golden/README.md).

### Reproduce

```bash
pip install -e ".[dev]"
OPENAI_API_KEY= make eval
make eval-check
```
