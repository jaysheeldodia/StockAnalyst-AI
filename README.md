# Stock Analyst

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
