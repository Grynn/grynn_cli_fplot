.PHONY: install clean test lint format coverage dev

install:
	uv tool install .

dev: 
	uv pip install ".[dev]"

test: install
	uv run pytest

coverage: dev
	uv run pytest --cov=src/grynn_cli_fplot --cov-report=term-missing

lint: dev
	uvx ruff check src tests
	uvx mypy src tests

format: dev
	uvx ruff format src tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf ./dist
	rm -rf ./build
	rm -rf ./venv
	rm -rf ./.venv
	rm -rf .coverage
	rm -rf htmlcov