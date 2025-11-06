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
fplot <ticker> --call --min-dte 300    # List long-dated calls (min 300 days)
fplot <ticker> --call --filter "dte>300"  # Filter using expressions
```

Examples:

- `fplot AAPL --call`
- `fplot TSLA --put --max 3m`
- `fplot AAPL --call --all`
- `fplot AAPL --call --min-dte 300 --all`  # Long-dated calls
- `fplot AAPL --call --filter "dte>10, dte<50"`  # 10-50 days to expiry

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
- `--min-dte <days>`: Minimum days to expiry (useful for long-dated options)
  - Example: `--min-dte 300` shows only options with 300+ days to expiry
- `--all`: Show all available expiries (overrides `--max`)

**Advanced Filtering with `--filter`:**

The `--filter` option supports complex filter expressions with logical operators:

- **Syntax:**
  - Comma (`,`) represents AND operation
  - Plus (`+`) represents OR operation
  - Comparison operators: `>`, `<`, `>=`, `<=`, `=`, `!=`
  - Parentheses for grouping: `(expr1 + expr2), expr3`

- **Filter Fields:**
  - `dte`: Days to expiry
  - `strike`: Strike price
  - `volume`: Option volume
  - `price`: Last price
  - `return`: Return metric (CAGR for calls, annualized return for puts)
  - `spot`: Current spot price

- **Examples:**
  - `--filter "dte>300"` - Options with more than 300 days to expiry
  - `--filter "dte>10, dte<50"` - Options between 10-50 days (AND operation)
  - `--filter "dte<30 + dte>300"` - Short-term OR long-dated (OR operation)
  - `--filter "strike>100, strike<200"` - Strike price between 100-200
  - `--filter "(dte>300 + dte<30), strike>150"` - Complex nested filters
  - `--filter "volume>=100"` - High volume options

- **Time Values:**
  - Time expressions like `2d15h`, `30m`, `1d` are supported
  - Units: `d` (days), `h` (hours), `m` (minutes), `s` (seconds)
  - Example: `--filter "lt_days<=2d15h"` (if custom fields support time values)

Options data is cached for 1 hour to improve performance and reduce API calls.
