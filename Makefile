.PHONY: dev test lint format seed example

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

