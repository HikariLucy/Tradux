.PHONY: help install dev test lint format run clean

help:
	@echo "Tradux Makefile"
	@echo "  make install  - Install dependencies in editable mode"
	@echo "  make dev      - Install dev dependencies"
	@echo "  make test     - Run pytest test suite"
	@echo "  make lint     - Run ruff linter"
	@echo "  make format   - Run ruff formatter"
	@echo "  make run      - Run uvicorn server locally"
	@echo "  make clean    - Remove build and cache files"

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage dist build *.egg-info
