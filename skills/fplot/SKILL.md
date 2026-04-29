---
name: fplot
description: Work on or use grynn-fplot, the financial plotting and options CLI, including comparative chart normalization, options filters, releases, and visual verification.
---

# fplot Agent Skill

Use this skill when working in the `grynn_cli_fplot` repository or when the user asks about `fplot` stock charts, comparative charts, options filters, releases, or PyPI publishing.

## Project

- Repository: `https://github.com/Grynn/grynn_cli_fplot`
- Package: `grynn-fplot`
- CLI entry point: `fplot`
- Main CLI module: `grynn_fplot/cli.py`
- Core data helpers: `grynn_fplot/core.py`
- Web UI/API: `grynn_fplot/index.html`, `grynn_fplot/serve.py`, `grynn_fplot/web_api.py`

## Development Defaults

- Use `uv` for all Python commands.
- Run the full suite with `uv run pytest -q`.
- Run lint on touched files with `uv run ruff check <paths>`.
- Use `rg` for code search.
- Use `apply_patch` for edits.

## Comparative Chart Checks

- Always include `IBKR,HOOD` when changing comparative chart behavior. `HOOD` has a later first valid date than `IBKR`, which catches staggered-history bugs.
- The initial view for `--since` should be clamped to the visible window at startup.
- Panning or zooming comparative charts should rebase normalized prices to the first valid visible point for each ticker, recompute drawdowns for the visible window, recompute visible AUC/CAGR labels, and compact y-limits to visible values.
- Setting only `xlim` is not enough when rebasing comparative charts. The plotted line and fill artists should be updated to the visible slice so hidden full-history values cannot leak into autoscale or line segments.

## Visual Verification

Use the non-interactive backend for repeatable screenshots:

```shell
MPLBACKEND=Agg uv run python - <<'PY'
from pathlib import Path
import matplotlib.pyplot as plt
from grynn_fplot.cli import display_cli_plot

out_dir = Path('/tmp/grynn_fplot_checks')
out_dir.mkdir(parents=True, exist_ok=True)

def fake_show():
    fig = plt.gcf()
    fig.savefig(out_dir / 'hood_ibkr_check.png', dpi=140)
    plt.close(fig)

plt.show = fake_show
display_cli_plot(['HOOD', 'IBKR'], '2y', '1d', False)
print(out_dir / 'hood_ibkr_check.png')
PY
```

Inspect the saved image when visual layout or chart behavior changes.

## Release Workflow

- Use `make bump` for patch releases. It runs tests, bumps `pyproject.toml` and `uv.lock`, commits, and tags locally.
- PyPI publish is handled by `.github/workflows/publish.yml` when a `v*` tag is pushed.
- Do not run `uv publish` locally unless the GitHub Action fails and the user asks for manual publishing.
- If additional docs or fixes are committed after `make bump`, retag locally before pushing so the release tag points to the final intended commit.
