from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.api.schemas import AnalyzeRequest, AnalyzeResponse
from app.services.analysis_service import AnalysisService

app = FastAPI(title="Stock Analyst API", version="0.1.0")
service = AnalysisService()

# Serve a lightweight HTML/CSS/JS UI (replacing Streamlit).
_web_dir = Path(__file__).resolve().parent.parent / "ui" / "web"
_static_dir = _web_dir / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(_web_dir / "index.html"))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    result = await service.analyze(request.ticker, horizon=request.horizon)
    return AnalyzeResponse(**result)


@app.get("/stream/{ticker}")
async def stream(ticker: str, horizon: str = "12m") -> StreamingResponse:
    async def event_source():
        async for event in service.stream_analysis(ticker, horizon=horizon):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
