# Display comparative stock price history

## Development

For development, install the package in editable mode with `make dev`

## Installation

`make install` installs fplot using `uv tool install .` making it available across the system.

Still in development, so not yet available on PyPI. Have to use make install instead of `uv tool install grynn_fplot`

## Usage

### Stock Plotting

```shell
fplot <ticker> [--since <date>] [--interval <interval>]
```

Examples:

- `fplot AAPL`
- `fplot AAPL --since 2020`
- `fplot AAPL,TSLA --since "mar 2023"`

### Options Listing

```shell
fplot <ticker> --call                  # List call options (default: 6 months max)
fplot <ticker> --put                   # List put options (default: 6 months max)
fplot <ticker> --call --max 3m         # List calls with 3 month max expiry
fplot <ticker> --put --all             # List all available put options
```

Examples:

- `fplot AAPL --call`
- `fplot TSLA --put --max 3m`
- `fplot AAPL --call --all`

The options output includes pricing and return metrics:
```
AAPL 225C 35DTE ($5.25, 18.5%)
AAPL 230C 35DTE ($3.10, 25.2%)
AAPL 235C 35DTE ($1.85, 35.1%)
```

Format: `TICKER STRIKE[C|P] DAYS_TO_EXPIRY (price, return_metric)`
- For calls: return_metric is CAGR to breakeven
- For puts: return_metric is annualized return

**Expiry Filtering Options:**
- `--max <time>`: Filter to show only options expiring within the specified time
  - Examples: `3m` (3 months), `6m` (6 months), `1y` (1 year), `2w` (2 weeks), `30d` (30 days)
  - Default: `6m` (6 months)
- `--all`: Show all available expiries (overrides `--max`)

Options data is cached for 1 hour to improve performance and reduce API calls.
