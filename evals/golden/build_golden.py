"""Build the golden set, eval corpus, and market fixtures from SEC XBRL and yfinance.

Every number written by this script is read from data.sec.gov companyfacts or yfinance at
build time. Run: python -m evals.golden.build_golden  (needs network access).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_PATH = ROOT / "evals" / "golden" / "stock_qa.jsonl"
CORPUS_PATH = ROOT / "evals" / "corpus" / "stock_corpus.jsonl"
FIXTURE_DIR = ROOT / "evals" / "fixtures" / "market"

SEC_UA = os.getenv("SEC_USER_AGENT", "StockAnalyst-AI eval harness https://github.com/jaysheeldodia/StockAnalyst-AI")

COMPANIES: dict[str, dict[str, str]] = {
    "AAPL": {"cik": "0000320193", "name": "Apple", "sector": "Technology"},
    "JPM": {"cik": "0000019617", "name": "JPMorgan Chase", "sector": "Financials"},
    "XOM": {"cik": "0000034088", "name": "Exxon Mobil", "sector": "Energy"},
    "JNJ": {"cik": "0000200406", "name": "Johnson & Johnson", "sector": "Health Care"},
    "WMT": {"cik": "0000104169", "name": "Walmart", "sector": "Consumer Staples"},
}

REVENUE_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenuesNetOfInterestExpense",
    "SalesRevenueNet",
]
NET_INCOME_TAGS = ["NetIncomeLoss", "ProfitLoss"]
PRETAX_TAGS = [
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
]
EPS_TAGS = ["EarningsPerShareDiluted"]
LIABILITIES_TAGS = ["Liabilities"]
EQUITY_TAGS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
LIAB_AND_EQUITY_TAGS = ["LiabilitiesAndStockholdersEquity"]


class MissingFact(RuntimeError):
    pass


def _filing_url(cik: str, accn: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/"


def _annual_series(facts: dict, tags: list[str], unit: str) -> tuple[str, dict[str, dict]]:
    """Return (tag, {period_end: fact}) for the tag whose annual 10-K series is most recent."""
    best: tuple[str, dict[str, dict]] | None = None
    for tag in tags:
        rows = facts.get(tag, {}).get("units", {}).get(unit, [])
        series: dict[str, dict] = {}
        for r in rows:
            if r.get("form") != "10-K" or "start" not in r:
                continue
            days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
            if not 350 <= days <= 380:
                continue
            prev = series.get(r["end"])
            if prev is None or r["filed"] > prev["filed"]:
                series[r["end"]] = r
        if series and (best is None or max(series) > max(best[1])):
            best = (tag, series)
    if best is None:
        raise MissingFact(f"no annual 10-K series for {tags}")
    return best


def _instant_series(facts: dict, tags: list[str], unit: str = "USD") -> tuple[str, dict[str, dict]]:
    for tag in tags:
        rows = facts.get(tag, {}).get("units", {}).get(unit, [])
        series: dict[str, dict] = {}
        for r in rows:
            if r.get("form") != "10-K" or "start" in r:
                continue
            prev = series.get(r["end"])
            if prev is None or r["filed"] > prev["filed"]:
                series[r["end"]] = r
        if series:
            return tag, series
    raise MissingFact(f"no instant 10-K series for {tags}")


def _bn(v: float) -> float:
    return round(v / 1e9, 2)


def _pct(num: float, den: float) -> float:
    return round(num / den * 100.0, 1)


def _yoy(cur: float, prev: float) -> float:
    return round((cur / prev - 1.0) * 100.0, 1)


def sec_facts(ticker: str, cik: str, client: httpx.Client) -> dict[str, Any]:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    resp = client.get(url)
    resp.raise_for_status()
    facts = resp.json()["facts"]["us-gaap"]

    rev_tag, rev = _annual_series(facts, REVENUE_TAGS, "USD")
    ends = sorted(rev)
    if len(ends) < 3:
        raise MissingFact(f"{ticker}: need 3 fiscal years of revenue, got {len(ends)}")
    e0, e1, e2 = ends[-1], ends[-2], ends[-3]

    ni_tag, ni = _annual_series(facts, NET_INCOME_TAGS, "USD")
    pt_tag, pt = _annual_series(facts, PRETAX_TAGS, "USD")
    eps_tag, eps = _annual_series(facts, EPS_TAGS, "USD/shares")
    eq_tag, eq = _instant_series(facts, EQUITY_TAGS)
    try:
        li_tag, li = _instant_series(facts, LIABILITIES_TAGS)
        liabilities = li[e0]["val"]
    except (MissingFact, KeyError):
        la_tag, la = _instant_series(facts, LIAB_AND_EQUITY_TAGS)
        li_tag = f"{la_tag} - {eq_tag}"
        liabilities = la[e0]["val"] - eq[e0]["val"]

    for name, series, end in [
        ("net income", ni, e0),
        ("net income prior", ni, e1),
        ("pretax", pt, e0),
        ("eps", eps, e0),
        ("eps prior", eps, e1),
        ("equity", eq, e0),
    ]:
        if end not in series:
            raise MissingFact(f"{ticker}: {name} missing for period ending {end}")

    latest = rev[e0]
    return {
        "fy": int(e0[:4]),
        "period_start": latest["start"],
        "period_end": e0,
        "prior_period_end": e1,
        "filing_url": _filing_url(cik, latest["accn"]),
        "prior_filing_url": _filing_url(cik, rev[e1]["accn"]),
        "concepts": {
            "revenue": rev_tag,
            "net_income": ni_tag,
            "pretax_income": pt_tag,
            "eps_diluted": eps_tag,
            "liabilities": li_tag,
            "equity": eq_tag,
        },
        "revenue": rev[e0]["val"],
        "revenue_prior": rev[e1]["val"],
        "revenue_prior2": rev[e2]["val"],
        "net_income": ni[e0]["val"],
        "net_income_prior": ni[e1]["val"],
        "pretax_income": pt[e0]["val"],
        "eps": eps[e0]["val"],
        "eps_prior": eps[e1]["val"],
        "liabilities": liabilities,
        "equity": eq[e0]["val"],
    }


def yf_facts(ticker: str) -> dict[str, Any]:
    import yfinance as yf

    info = yf.Ticker(ticker).info or {}
    keys = ["currentPrice", "targetMeanPrice", "numberOfAnalystOpinions", "forwardEps", "forwardPE", "beta"]
    out = {k: info.get(k) for k in keys}
    missing = [k for k, v in out.items() if v is None]
    if missing:
        raise MissingFact(f"{ticker}: yfinance missing {missing}")
    return out


def build_ticker(ticker: str, meta: dict[str, str], sec: dict, yfd: dict, accessed: str):
    name, fy = meta["name"], sec["fy"]
    sec_src = {"url": sec["filing_url"], "accessed": accessed, "provider": "SEC EDGAR XBRL companyfacts"}
    yf_src = {"url": f"https://finance.yahoo.com/quote/{ticker}/analysis", "accessed": accessed, "provider": "yfinance"}

    rev_bn, rev_p_bn, rev_p2_bn = _bn(sec["revenue"]), _bn(sec["revenue_prior"]), _bn(sec["revenue_prior2"])
    rev_yoy, rev_p_yoy = _yoy(sec["revenue"], sec["revenue_prior"]), _yoy(sec["revenue_prior"], sec["revenue_prior2"])
    ni_bn, ni_p_bn = _bn(sec["net_income"]), _bn(sec["net_income_prior"])
    ni_yoy = _yoy(sec["net_income"], sec["net_income_prior"])
    net_margin = _pct(sec["net_income"], sec["revenue"])
    pt_bn, pt_margin = _bn(sec["pretax_income"]), _pct(sec["pretax_income"], sec["revenue"])
    eps, eps_p = round(sec["eps"], 2), round(sec["eps_prior"], 2)
    eps_yoy = _yoy(sec["eps"], sec["eps_prior"])
    li_bn, eq_bn = _bn(sec["liabilities"]), _bn(sec["equity"])
    l2e = round(sec["liabilities"] / sec["equity"], 2)
    price, target = round(yfd["currentPrice"], 2), round(yfd["targetMeanPrice"], 2)
    upside = _yoy(yfd["targetMeanPrice"], yfd["currentPrice"])
    fwd_eps, fwd_pe, beta = round(yfd["forwardEps"], 2), round(yfd["forwardPE"], 1), round(yfd["beta"], 2)
    n_analysts = int(yfd["numberOfAnalystOpinions"])
    period = f"fiscal year {fy} (period {sec['period_start']} to {sec['period_end']})"
    prefix = f"{name} ({ticker})"

    corpus = [
        (f"{ticker.lower()}_10k_fy{fy}_revenue", sec["filing_url"], "financial_filings",
         f"{prefix} Form 10-K, {period}: total revenue was ${rev_bn:.2f} billion, compared with "
         f"${rev_p_bn:.2f} billion in fiscal {fy - 1}, a year-over-year change of {rev_yoy:.1f}%."),
        (f"{ticker.lower()}_10k_fy{fy - 1}_revenue", sec["prior_filing_url"], "financial_filings",
         f"{prefix} Form 10-K, fiscal year {fy - 1}: total revenue was ${rev_p_bn:.2f} billion, "
         f"compared with ${rev_p2_bn:.2f} billion in fiscal {fy - 2}, a year-over-year change of {rev_p_yoy:.1f}%."),
        (f"{ticker.lower()}_10k_fy{fy}_net_income", sec["filing_url"], "financial_filings",
         f"{prefix} Form 10-K, {period}: net income was ${ni_bn:.2f} billion versus ${ni_p_bn:.2f} billion "
         f"in fiscal {fy - 1} ({ni_yoy:.1f}% year over year), a net margin of {net_margin:.1f}% of revenue."),
        (f"{ticker.lower()}_10k_fy{fy}_pretax", sec["filing_url"], "financial_filings",
         f"{prefix} Form 10-K, {period}: income before income taxes was ${pt_bn:.2f} billion, "
         f"a pre-tax margin of {pt_margin:.1f}% of total revenue."),
        (f"{ticker.lower()}_10k_fy{fy}_eps", sec["filing_url"], "financial_filings",
         f"{prefix} Form 10-K, {period}: diluted earnings per share were ${eps:.2f}, compared with "
         f"${eps_p:.2f} in fiscal {fy - 1} ({eps_yoy:.1f}% year over year)."),
        (f"{ticker.lower()}_10k_fy{fy}_balance_sheet", sec["filing_url"], "financial_filings",
         f"{prefix} Form 10-K balance sheet at {sec['period_end']}: total liabilities were ${li_bn:.2f} billion "
         f"and shareholders' equity was ${eq_bn:.2f} billion, a liabilities-to-equity ratio of {l2e:.2f}."),
        (f"{ticker.lower()}_yf_analyst_{accessed}", yf_src["url"], "analyst_estimates",
         f"{prefix} analyst consensus as of {accessed} (yfinance): mean price target ${target:.2f} from "
         f"{n_analysts} analysts versus a current price of ${price:.2f}, implying {upside:.1f}%. "
         f"Forward EPS estimate ${fwd_eps:.2f}, forward P/E {fwd_pe:.1f}, beta {beta:.2f}."),
    ]
    corpus_rows = [
        {"id": cid, "text": text,
         "metadata": {"ticker": ticker, "source_type": st, "url": url, "accessed": accessed}}
        for cid, url, st, text in corpus
    ]

    def row(qid, qtype, question, answer_key, claims, reference, src, must_refuse=False):
        return {
            "id": f"{ticker.lower()}_{qid}",
            "ticker": ticker,
            "horizon": "12m",
            "type": qtype,
            "question": question,
            "answer_key": answer_key,
            "claims_required": claims,
            "reference": reference,
            "source": src,
            "must_refuse": must_refuse,
        }

    sec_src_c = {**sec_src, "concepts": sec["concepts"]}
    sec_src_prior = {**sec_src_c, "url": sec["prior_filing_url"]}
    rows = [
        row(f"revenue_fy{fy}", "revenue",
            f"What was {name}'s total revenue in fiscal {fy}, and how did it change year over year?",
            {"total_revenue_usd_bn": rev_bn, "yoy_change_pct": rev_yoy},
            ["total revenue", "year-over-year change"],
            f"{name}'s total revenue in fiscal {fy} was ${rev_bn:.2f} billion, a {rev_yoy:.1f}% change from ${rev_p_bn:.2f} billion in fiscal {fy - 1}.",
            sec_src_c),
        row(f"revenue_fy{fy - 1}", "revenue",
            f"What was {name}'s total revenue in fiscal {fy - 1}, and how did it compare with fiscal {fy - 2}?",
            {"total_revenue_usd_bn": rev_p_bn, "yoy_change_pct": rev_p_yoy},
            ["total revenue", "year-over-year change"],
            f"{name}'s total revenue in fiscal {fy - 1} was ${rev_p_bn:.2f} billion, a {rev_p_yoy:.1f}% change from ${rev_p2_bn:.2f} billion in fiscal {fy - 2}.",
            sec_src_prior),
        row(f"net_margin_fy{fy}", "margin",
            f"What was {name}'s net profit margin in fiscal {fy}?",
            {"net_income_usd_bn": ni_bn, "net_margin_pct": net_margin},
            ["net income", "net margin"],
            f"{name} earned net income of ${ni_bn:.2f} billion in fiscal {fy}, a net margin of {net_margin:.1f}%.",
            sec_src_c),
        row(f"pretax_margin_fy{fy}", "margin",
            f"What was {name}'s pre-tax margin in fiscal {fy}?",
            {"pretax_income_usd_bn": pt_bn, "pretax_margin_pct": pt_margin},
            ["pre-tax income", "pre-tax margin"],
            f"{name}'s income before taxes in fiscal {fy} was ${pt_bn:.2f} billion, a pre-tax margin of {pt_margin:.1f}%.",
            sec_src_c),
        row(f"leverage_fy{fy}", "risk",
            f"How leveraged is {name}'s balance sheet: what were total liabilities relative to shareholders' equity at the end of fiscal {fy}?",
            {"total_liabilities_usd_bn": li_bn, "stockholders_equity_usd_bn": eq_bn, "liabilities_to_equity": l2e},
            ["total liabilities", "shareholders' equity", "leverage ratio"],
            f"At the end of fiscal {fy}, {name} had total liabilities of ${li_bn:.2f} billion and shareholders' equity of ${eq_bn:.2f} billion, a liabilities-to-equity ratio of {l2e:.2f}.",
            sec_src_c),
        row("beta", "risk",
            f"How volatile is {ticker} stock relative to the market, as measured by beta?",
            {"beta": beta},
            ["beta"],
            f"{ticker} has a beta of {beta:.2f} according to yfinance as of {accessed}.",
            yf_src),
        row(f"net_income_fy{fy}_vs_fy{fy - 1}", "comparison",
            f"How did {name}'s net income in fiscal {fy} compare with fiscal {fy - 1}?",
            {"net_income_usd_bn": ni_bn, "prior_net_income_usd_bn": ni_p_bn, "yoy_change_pct": ni_yoy},
            ["net income", "prior-year net income", "year-over-year change"],
            f"{name}'s net income was ${ni_bn:.2f} billion in fiscal {fy} versus ${ni_p_bn:.2f} billion in fiscal {fy - 1}, a {ni_yoy:.1f}% change.",
            sec_src_c),
        row(f"eps_fy{fy}_vs_fy{fy - 1}", "comparison",
            f"How did {name}'s diluted EPS in fiscal {fy} compare with fiscal {fy - 1}?",
            {"eps_diluted_usd": eps, "prior_eps_diluted_usd": eps_p, "yoy_change_pct": eps_yoy},
            ["diluted EPS", "prior-year diluted EPS", "year-over-year change"],
            f"{name}'s diluted EPS was ${eps:.2f} in fiscal {fy} versus ${eps_p:.2f} in fiscal {fy - 1}, a {eps_yoy:.1f}% change.",
            sec_src_c),
        row("price_target", "outlook",
            f"What is the analyst consensus price target for {ticker}, and what upside or downside does it imply versus the current price?",
            {"target_mean_price_usd": target, "current_price_usd": price, "implied_return_pct": upside},
            ["consensus price target", "current price", "implied upside or downside"],
            f"As of {accessed}, the mean analyst price target for {ticker} was ${target:.2f} versus a price of ${price:.2f}, implying {upside:.1f}%.",
            yf_src),
        row("forward_eps", "outlook",
            f"What forward EPS do analysts expect for {ticker}, and what forward P/E does that imply?",
            {"forward_eps_usd": fwd_eps, "forward_pe": fwd_pe},
            ["forward EPS", "forward P/E"],
            f"As of {accessed}, analysts expected forward EPS of ${fwd_eps:.2f} for {ticker}, a forward P/E of {fwd_pe:.1f}.",
            yf_src),
        row("refuse_revenue_fy2031", "revenue",
            f"What will {name}'s exact total revenue be in fiscal 2031?",
            None, [],
            "This cannot be answered: no filing or data source reports revenue for a future fiscal year.",
            sec_src, must_refuse=True),
        row("refuse_internal_forecast", "outlook",
            f"What does {name}'s unpublished internal sales forecast for next quarter show?",
            None, [],
            "This cannot be answered: internal forecasts are not public and appear in no filing.",
            sec_src, must_refuse=True),
    ]
    return rows, corpus_rows


def main() -> int:
    from app.market.yfinance_snapshot import fetch_market_snapshot

    accessed = datetime.now(timezone.utc).date().isoformat()
    all_rows: list[dict] = []
    all_chunks: list[dict] = []
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(headers={"User-Agent": SEC_UA}, timeout=60) as client:
        for ticker, meta in COMPANIES.items():
            sec = sec_facts(ticker, meta["cik"], client)
            yfd = yf_facts(ticker)
            rows, chunks = build_ticker(ticker, meta, sec, yfd, accessed)
            all_rows.extend(rows)
            all_chunks.extend(chunks)
            snapshot = fetch_market_snapshot(ticker)
            if snapshot.get("error"):
                raise RuntimeError(f"{ticker}: market snapshot error {snapshot['error']}")
            (FIXTURE_DIR / f"{ticker}.json").write_text(
                json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            print(f"{ticker}: fiscal {sec['fy']} ({sec['period_end']}), {len(rows)} rows, {len(chunks)} chunks")

    GOLDEN_PATH.write_text("".join(json.dumps(r) + "\n" for r in all_rows), encoding="utf-8")
    CORPUS_PATH.write_text("".join(json.dumps(c) + "\n" for c in all_chunks), encoding="utf-8")
    print(f"wrote {len(all_rows)} rows -> {GOLDEN_PATH.relative_to(ROOT)}")
    print(f"wrote {len(all_chunks)} chunks -> {CORPUS_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
