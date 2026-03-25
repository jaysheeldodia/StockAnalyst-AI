# Stock Analyst Repo

This repo contains a multi-agent stock research system built with **LangGraph** and served via **FastAPI**, with a small web UI.

## Common Commands

- Run the API (dev):
  - `make dev`
- Run tests:
  - `make test`
- Seed Chroma documents for RAG:
  - `make seed`
- Run the example analysis script:
  - `make example`

## Key Directories

- `app/`: application code (agents, graph orchestration, API, storage, UI assets)
- `tests/`: automated tests
- `examples/`: runnable example scripts
- `data/`: local persistent artifacts (Chroma + SQLite). These are ignored by `.gitignore`.

