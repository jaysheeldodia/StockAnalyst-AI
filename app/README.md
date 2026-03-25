# `app/` Package

This package contains the application code for StockAnalyst.

Key modules:

- `app.api`: FastAPI entrypoints and request/response schemas
- `app.graph`: LangGraph orchestration (planner, nodes, report flow, loops)
- `app.agents`: Individual agent implementations (news, financials, sentiment, etc.)
- `app.providers`: Data/service providers used by agents
- `app.retrieval`: RAG retrieval utilities (ChromaDB)
- `app.storage`: Persistence layers (SQLite / document stores)
- `app.ui`: Web UI assets served by the API
- `app.bootstrap`: Seeding utilities for local dev (e.g., RAG documents)

