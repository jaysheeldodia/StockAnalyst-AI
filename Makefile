.PHONY: dev test lint format seed example eval eval-smoke eval-check eval-baseline

PYTHON ?= python

dev:
	uvicorn app.api.main:app --reload

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

seed:
	python -m app.bootstrap

example:
	python examples/run_example.py

# Full golden set. Judged layer only with EVAL_JUDGE=1. Caps: EVAL_MAX_USD, EVAL_MAX_CASES.
eval:
	$(PYTHON) -m evals.run_eval --profile full

# 5 cases, agent LLM off, no judge; then gate against the smoke baseline.
eval-smoke:
	$(PYTHON) -m evals.run_eval --profile smoke
	$(PYTHON) -m evals.compare_baseline --profile smoke

# Gate the newest result in evals/results against evals/baseline.json.
eval-check:
	$(PYTHON) -m evals.compare_baseline

# Re-measure both profiles and overwrite evals/baseline.json.
eval-baseline:
	$(PYTHON) -m evals.run_eval --profile smoke
	$(PYTHON) -m evals.run_eval --profile full
	$(PYTHON) -m evals.compare_baseline --update-baseline
