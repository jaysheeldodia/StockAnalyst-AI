from __future__ import annotations


def build_hyde_query(ticker: str, objective: str) -> str:
    return (
        f"Hypothetical analyst memo for {ticker}: "
        f"This document explains {objective}, cites management commentary, "
        "financial trends, macro context, and risks affecting the stock."
    )
