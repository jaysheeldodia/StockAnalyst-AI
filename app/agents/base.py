from __future__ import annotations

from dataclasses import dataclass

from app.models import Signal
from app.retrieval.rag import RetrievalService


@dataclass(slots=True)
class AgentResult:
    agent_name: str
    signals: list[dict]
    retrieved_context: list[dict]


class BaseResearchAgent:
    agent_name: str
    source_type: str

    def __init__(self, retrieval: RetrievalService) -> None:
        self.retrieval = retrieval

    async def run(self, ticker: str, plan: dict, iteration_count: int = 0) -> AgentResult:
        raise NotImplementedError

    def _serialize_signals(self, agent_name: str, source_type: str, signals: list[dict]) -> list[dict]:
        serialized: list[dict] = []
        for signal in signals:
            model = Signal(**signal, source_type=source_type, agent=agent_name)
            serialized.append(model.model_dump())
        return serialized
