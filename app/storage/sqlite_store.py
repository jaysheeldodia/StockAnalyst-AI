from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.config import get_config

try:
    import aiosqlite
except ImportError:  # pragma: no cover
    aiosqlite = None


SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    report TEXT NOT NULL,
    thesis_json TEXT NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    agent_name TEXT NOT NULL,
    signal_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    faithfulness REAL,
    answer_relevance REAL,
    context_precision REAL,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    horizon TEXT NOT NULL,
    as_of_utc TEXT NOT NULL,
    entry_price REAL,
    recommendation TEXT,
    confidence_score REAL,
    fair_value_low REAL,
    fair_value_base REAL,
    fair_value_high REAL,
    predicted_return_base_pct REAL,
    realized_return_base_pct REAL,
    realized_at TEXT,
    created_at TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self) -> None:
        self.db_path = get_config().sqlite_path

    async def initialize(self) -> None:
        if aiosqlite is not None:
            async with aiosqlite.connect(self.db_path) as db:
                await db.executescript(SCHEMA)
                await db.commit()
            return
        await asyncio.to_thread(self._initialize_sync)

    async def save_report(self, ticker: str, report: str, thesis: dict[str, Any]) -> None:
        params = (ticker, report, json.dumps(thesis), datetime.now(timezone.utc).isoformat())
        if aiosqlite is not None:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO reports (ticker, report, thesis_json, generated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    params,
                )
                await db.commit()
            return
        await asyncio.to_thread(
            self._execute_sync,
            """
            INSERT INTO reports (ticker, report, thesis_json, generated_at)
            VALUES (?, ?, ?, ?)
            """,
            [params],
        )

    async def save_signals(self, ticker: str, iteration: int, agent_name: str, signals: list[dict]) -> None:
        params = [
            (
                ticker,
                iteration,
                agent_name,
                json.dumps(signal),
                datetime.now(timezone.utc).isoformat(),
            )
            for signal in signals
        ]
        if aiosqlite is not None:
            async with aiosqlite.connect(self.db_path) as db:
                for row in params:
                    await db.execute(
                        """
                        INSERT INTO signals (ticker, iteration, agent_name, signal_json, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        row,
                    )
                await db.commit()
            return
        await asyncio.to_thread(
            self._execute_sync,
            """
            INSERT INTO signals (ticker, iteration, agent_name, signal_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            params,
        )

    async def save_evaluation(
        self,
        ticker: str,
        faithfulness: float | None,
        answer_relevance: float | None,
        context_precision: float | None,
        notes: str | None,
    ) -> None:
        params = (
            ticker,
            faithfulness,
            answer_relevance,
            context_precision,
            notes,
            datetime.now(timezone.utc).isoformat(),
        )
        if aiosqlite is not None:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO evaluations (
                        ticker, faithfulness, answer_relevance, context_precision, notes, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
                await db.commit()
            return
        await asyncio.to_thread(
            self._execute_sync,
            """
            INSERT INTO evaluations (
                ticker, faithfulness, answer_relevance, context_precision, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [params],
        )

    async def save_prediction_baseline(
        self,
        *,
        ticker: str,
        horizon: str,
        as_of_utc: str,
        entry_price: float | None,
        recommendation: str | None,
        confidence_score: float | None,
        fair_value_low: float | None,
        fair_value_base: float | None,
        fair_value_high: float | None,
        predicted_return_base_pct: float | None,
    ) -> None:
        params = (
            ticker,
            horizon,
            as_of_utc,
            entry_price,
            recommendation,
            confidence_score,
            fair_value_low,
            fair_value_base,
            fair_value_high,
            predicted_return_base_pct,
            None,  # realized_return_base_pct placeholder
            None,  # realized_at placeholder
            datetime.now(timezone.utc).isoformat(),
        )

        if aiosqlite is not None:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO predictions (
                        ticker, horizon, as_of_utc, entry_price, recommendation,
                        confidence_score, fair_value_low, fair_value_base, fair_value_high,
                        predicted_return_base_pct, realized_return_base_pct, realized_at, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                )
                await db.commit()
            return

        await asyncio.to_thread(
            self._execute_sync,
            """
            INSERT INTO predictions (
                ticker, horizon, as_of_utc, entry_price, recommendation,
                confidence_score, fair_value_low, fair_value_base, fair_value_high,
                predicted_return_base_pct, realized_return_base_pct, realized_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [params],
        )

    def _initialize_sync(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executescript(SCHEMA)
            db.commit()

    def _execute_sync(self, query: str, rows: list[tuple[Any, ...]]) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.executemany(query, rows)
            db.commit()
