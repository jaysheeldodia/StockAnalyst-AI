from __future__ import annotations

from app.agents.base import AgentResult, BaseResearchAgent
from app.llm.signals import generate_signals_with_llm
from app.providers.sentiment import SentimentProvider


class SentimentAgent(BaseResearchAgent):
    agent_name = "sentiment_agent"
    source_type = "social_media"
    _objective = "social sentiment and retail investor narratives"

    def __init__(self, retrieval) -> None:
        super().__init__(retrieval)
        self.provider = SentimentProvider()

    async def run(self, ticker: str, plan: dict, iteration_count: int = 0) -> AgentResult:
        context = await self.retrieval.aretrieve(ticker, self._objective)
        raw = await generate_signals_with_llm(
            agent_name=self.agent_name,
            ticker=ticker,
            retrieval_objective=self._objective,
            retrieved_context=context,
            plan=plan,
            iteration_count=iteration_count,
        )
        if not raw:
            raw = await self.provider.fetch(ticker, plan)
        return AgentResult(
            agent_name=self.agent_name,
            signals=self._serialize_signals(self.agent_name, self.source_type, raw),
            retrieved_context=context,
        )
