# Golden set

`stock_qa.jsonl` holds 60 cases: 50 answerable and 10 that must be refused. They cover
five tickers from five sectors (AAPL, JPM, XOM, JNJ, WMT) and five question types
(`revenue`, `margin`, `risk`, `comparison`, `outlook`).

Every number comes from SEC EDGAR XBRL `companyfacts` or `yfinance`. The script
`build_golden.py` reads them and writes the rows. Nobody types a figure by hand. The same
run also writes the retrieval corpus (`evals/corpus/stock_corpus.jsonl`) and the replayed
market snapshots (`evals/fixtures/market/<TICKER>.json`).

## Schema

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | str | Unique, `<ticker>_<slug>` |
| `ticker` | str | Ticker passed to `AnalysisService.analyze()` |
| `horizon` | str | Horizon passed to `analyze()`, e.g. `12m` |
| `type` | str | One of `revenue`, `margin`, `risk`, `comparison`, `outlook` |
| `question` | str | The analyst question |
| `answer_key` | object or null | Metric name to number. `null` when `must_refuse` is true |
| `claims_required` | list[str] | Claims a complete answer states. Empty for refusals |
| `reference` | str | Reference answer for Ragas (`context_precision`, `context_recall`) |
| `source.url` | str | SEC filing index or Yahoo Finance page the numbers come from |
| `source.accessed` | str | ISO date the source was read |
| `source.provider` | str | `SEC EDGAR XBRL companyfacts` or `yfinance` |
| `source.concepts` | object | SEC rows only: the XBRL concept behind each number |
| `must_refuse` | bool | True when no source can answer the question |

Units: `*_usd_bn` is billions of USD to 2 decimals, `*_pct` is percent to 1 decimal,
`*_usd` is USD to 2 decimals, and ratios are to 2 decimals. Fiscal years are named by the
calendar year of the period end. Walmart's year ending 2026-01-31 is therefore fiscal 2026.

## Worked example

```json
{"id": "aapl_revenue_fy2024", "ticker": "AAPL", "horizon": "12m", "type": "revenue",
 "question": "What was Apple's total revenue in fiscal 2024, and how did it compare with fiscal 2023?",
 "answer_key": {"total_revenue_usd_bn": 391.04, "yoy_change_pct": 2.0},
 "claims_required": ["total revenue", "year-over-year change"],
 "reference": "Apple's total revenue in fiscal 2024 was $391.04 billion, a 2.0% change from $383.29 billion in fiscal 2023.",
 "source": {"url": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/",
            "accessed": "2026-10-14", "provider": "SEC EDGAR XBRL companyfacts",
            "concepts": {"revenue": "RevenueFromContractWithCustomerExcludingAssessedTax"}},
 "must_refuse": false}
```

`391.04` is the XBRL value `391035000000` for the period 2023-10-01 to 2024-09-28,
divided by 1e9. `2.0` is `391035 / 383285 - 1`, as a percentage.

## Adding a case

1. Add the company to `COMPANIES` in `build_golden.py`, or add a question to `build_ticker()`.
   Read every number from the fetched SEC or yfinance data. Never use a literal.
2. Run `python -m evals.golden.build_golden` with network access.
3. Run `pytest tests/test_golden_schema.py`. Update the expected counts there if the
   split changes on purpose.
4. Changing the file changes the dataset hash. Re-run `make eval-baseline` and commit the
   new `evals/baseline.json` in the same pull request.
