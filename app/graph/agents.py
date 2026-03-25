from __future__ import annotations

from app.agents.financials_agent import FinancialsAgent
from app.agents.macro_agent import MacroAgent
from app.agents.news_agent import NewsAgent
from app.agents.sentiment_agent import SentimentAgent
from app.agents.transcript_agent import TranscriptAgent
from app.observability import traced
from app.retrieval.rag import RetrievalService
from app.state import GraphState
from app.storage.sqlite_store import SQLiteStore


def _raw_payload(result) -> dict:
    return {
        "agent_name": result.agent_name,
        "signals": result.signals,
        "retrieved_context": result.retrieved_context,
        "iteration": None,
    }


@traced("news_agent_node")
async def news_agent_node(state: GraphState) -> GraphState:
    agent = NewsAgent(RetrievalService())
    result = await agent.run(state["ticker"], state["plan"], state["iteration_count"])
    await SQLiteStore().save_signals(state["ticker"], state["iteration_count"], result.agent_name, result.signals)
    payload = _raw_payload(result)
    payload["iteration"] = state["iteration_count"]
    return {"raw_results": [payload]}


@traced("transcript_agent_node")
async def transcript_agent_node(state: GraphState) -> GraphState:
    agent = TranscriptAgent(RetrievalService())
    result = await agent.run(state["ticker"], state["plan"], state["iteration_count"])
    await SQLiteStore().save_signals(state["ticker"], state["iteration_count"], result.agent_name, result.signals)
    payload = _raw_payload(result)
    payload["iteration"] = state["iteration_count"]
    return {"raw_results": [payload]}


@traced("financials_agent_node")
async def financials_agent_node(state: GraphState) -> GraphState:
    agent = FinancialsAgent(RetrievalService())
    result = await agent.run(state["ticker"], state["plan"], state["iteration_count"])
    await SQLiteStore().save_signals(state["ticker"], state["iteration_count"], result.agent_name, result.signals)
    payload = _raw_payload(result)
    payload["iteration"] = state["iteration_count"]
    return {"raw_results": [payload]}


@traced("sentiment_agent_node")
async def sentiment_agent_node(state: GraphState) -> GraphState:
    agent = SentimentAgent(RetrievalService())
    result = await agent.run(state["ticker"], state["plan"], state["iteration_count"])
    await SQLiteStore().save_signals(state["ticker"], state["iteration_count"], result.agent_name, result.signals)
    payload = _raw_payload(result)
    payload["iteration"] = state["iteration_count"]
    return {"raw_results": [payload]}


@traced("macro_agent_node")
async def macro_agent_node(state: GraphState) -> GraphState:
    agent = MacroAgent(RetrievalService())
    result = await agent.run(state["ticker"], state["plan"], state["iteration_count"])
    await SQLiteStore().save_signals(state["ticker"], state["iteration_count"], result.agent_name, result.signals)
    payload = _raw_payload(result)
    payload["iteration"] = state["iteration_count"]
    return {"raw_results": [payload]}
