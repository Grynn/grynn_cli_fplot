.PHONY: install clean test lint format coverage dev bump pre-commit pre-commit-install build publish

test:
	uv run pytest

pre-commit: dev
	uvx pre-commit run --all-files

pre-commit-install:
	uvx pre-commit install

work-tree-is-clean:
	@# Check if the working directory is clean
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory is not clean. Please commit or stash your changes first."; \
		git status --short; \
		exit 1; \
	else \
		echo "Working directory is clean."; \
	fi

bump: test pre-commit-install work-tree-is-clean
	@# 1. Bump version using uv
	@uv version --bump patch
	@# 2. Commit changes (work tree was clean before, so only version files changed)
	@new_version=$$(uv version --short) && \
	git commit -am "Bump version => v$$new_version" && \
	git tag "v$$new_version" && \
	echo "Created git commit and tag v$$new_version"

install:
	uv tool install --upgrade-package "grynn_fplot" "grynn_fplot @ $$PWD"

dev:
	uv sync --all-extras

coverage: dev
	uv run pytest --cov=src/grynn_cli_fplot --cov-report=term-missing

lint: dev
	uvx ruff check

format: dev
	uvx ruff format

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

build: clean
	uv build

publish: build
	@echo "Publishing to PyPI..."
	@echo "Note: For CI/CD, use GitHub Actions with trusted publishing instead."
	uv publish
