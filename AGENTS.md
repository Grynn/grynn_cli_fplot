# Agent Notes for grynn_fplot

- Use `uv` for dependency and test commands. Prefer `uv run pytest -q` for the full suite and `uv run ruff check ...` for lint checks.
- For release work, use `make bump`. It runs tests, installs pre-commit hooks, updates `pyproject.toml` and `uv.lock`, creates the version commit, and tags `HEAD`.
- PyPI publishing is handled by `.github/workflows/publish.yml` on `v*` tag pushes. Do not run `uv publish` locally unless the GitHub Action fails and the user explicitly wants a manual publish.
- If docs or follow-up fixes are added after `make bump`, ensure the release tag points at the final intended commit before pushing. Retag locally only before the tag has been pushed.
- Pre-commit may reformat files and abort the commit. When that happens, inspect `git status`, stage the hook edits, and rerun the commit.
- For comparative chart work, test with `IBKR,HOOD` because `HOOD` starts later than `IBKR`. Align comparisons on the first date where all compared tickers have valid data.
- For matplotlib chart verification, use `MPLBACKEND=Agg` and monkeypatch `plt.show` to save screenshots under `/tmp/grynn_fplot_checks`. Inspect both initial and simulated panned views.
- When rebasing/compressing comparative charts after pan or zoom, update the plotted artist data to the visible slice itself. Setting only `xlim` can leave hidden full-history data influencing line segments, autoscale, or visual output.
