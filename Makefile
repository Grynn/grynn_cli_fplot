.PHONY: install clean test lint format coverage dev bump bump_patch pre-commit pre-commit-install build publish

test:
	uv run pytest

pre-commit: dev
	uvx pre-commit run --all-files

pre-commit-install:
	uvx pre-commit install

bump: bump_patch

bump_patch:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Error: Working directory is not clean. Please commit or stash your changes first."; \
		git status --short; \
		exit 1; \
	fi
	@current_version=$$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/'); \
	new_version=$$(python3 -c "v='$$current_version'.split('.'); v[2]=str(int(v[2])+1); print('.'.join(v))"); \
	sed -i '' "s/^version = \".*\"/version = \"$$new_version\"/" pyproject.toml; \
	echo "Version bumped from $$current_version to $$new_version"; \
	git add pyproject.toml; \
	git commit -m "Bump version to $$new_version"; \
	git tag "v$$new_version"; \
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
