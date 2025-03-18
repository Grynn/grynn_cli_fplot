.PHONY: install clean test lint format coverage dev

test: 
	uv run pytest

install:
	uv tool install --upgrade-package "grynn_fplot" "grynn_fplot @ $$PWD"

dev: 
	uv sync --all-extras

coverage: dev
	uv run pytest --cov=src/grynn_cli_fplot --cov-report=term-missing

lint: dev
	uvx ruff check 

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