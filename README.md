# fplot - Financial Plotting & Options Analysis CLI

[![PyPI version](https://img.shields.io/pypi/v/grynn-fplot.svg)](https://pypi.org/project/grynn-fplot/)
[![Python versions](https://img.shields.io/pypi/pyversions/grynn-fplot.svg)](https://pypi.org/project/grynn-fplot/)

A command-line tool for plotting comparative stock price history and analyzing options contracts.

## Installation

### From PyPI

```shell
pip install grynn-fplot
```

Or with uv:

```shell
uv tool install grynn-fplot
```

### From Source

For development, install the package in editable mode:

```shell
make dev
```

Or install locally:

```shell
make install  # Uses uv tool install .
```

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
fplot <ticker> --call --min-dte 1y     # List long-dated calls (min 1 year)
fplot <ticker> --call --filter "dte>1y"  # Filter using time expressions
```

Examples:

- `fplot AAPL --call`
- `fplot TSLA --put --max 3m`
- `fplot AAPL --call --all`
- `fplot AAPL --call --min-dte 1y`  # Long-dated calls (1+ year)
- `fplot AAPL --call --min-dte 6m`  # Calls with 6+ months to expiry
- `fplot AAPL --call --filter "dte>10, dte<50"`  # 10-50 days to expiry
- `fplot AAPL --call --filter "dte>1y"`  # Options with 1+ year to expiry

The output format differs for calls and puts:

**Calls** include leverage and efficiency (useful for LEAPs):
```
AAPL 225C 35DTE ($5.25, 18.5%, 19.0x, eff:45)
AAPL 230C 35DTE ($3.10, 25.2%, 32.3x, eff:78)
```
Format: `TICKER STRIKE_C DTE (price, CAGR, leverage, eff:percentile)`

**Puts** display a table with spot price, expiry, strike, breakeven, volume, IV, and AR with premiums:
```
spot = $235.50

Expiry               Strike        Breakeven    Vol     IV   LT  AR: ask / bid / last
-------------------------------------------------------------------------------------
27/Mar/25 (35d)         220   $217.85 (-7.5%)    150   32%   1d  ask: $3.50 (28%) | bid: $2.80 (20%) | last: $3.10 (25%)
27/Mar/25 (35d)         215   $213.60 (-9.3%)     85   30%   3d  ask: $2.20 (18%) | bid: $1.60 (12%) | last: $1.90 (15%)
```

**Return metrics:**
- Calls: CAGR to breakeven
- Puts: AR = premium / capital-at-risk, annualized (capital-at-risk = strike - premium)

**Leverage & Efficiency (calls only):**
- Leverage: Implied leverage (Ω = Δ × S/O) where Δ is Black-Scholes delta, S is spot price, O is option price
  - Delta calculated using actual implied volatility from Yahoo Finance
  - Shows "N/A" if implied volatility is not available
  - Shows the percentage change in option value for a 1% change in stock price
  - Example: 10x leverage means a 1% stock move results in ~10% option move
- Efficiency: Percentile rank (0-100) of leverage/CAGR ratio
  - Higher = better (high leverage with low required stock movement)
  - 80+ = top 20% most efficient options
  - Shows "N/A" if leverage or return unavailable

**Expiry Filtering Options:**
- `--max <time>`: Filter to show only options expiring within the specified time
  - Examples: `3m` (3 months), `6m` (6 months), `1y` (1 year), `2w` (2 weeks), `30d` (30 days)
  - Default: `6m` (6 months)
- `--min-dte <time>`: Minimum days to expiry (useful for long-dated options)
  - Accepts plain days or time expressions: `300`, `1y`, `1.5y`, `6m`, `2w`
  - Examples: `--min-dte 1y` (1+ year), `--min-dte 6m` (6+ months)
  - Note: Using `--min-dte` automatically enables `--all` behavior
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
  - `volume`: Option volume
  - `price`: Last price
  - `return`, `ret`, `ar`: Return metric (CAGR for calls, AR for puts) - all aliases work
  - `strike_pct`, `sp`: Strike percentage above/below spot (positive = above spot, negative = below spot)
  - `lt_days`: Days since last trade (useful for filtering stale options)
  - `leverage`, `lev`: Implied leverage, calls only (Ω = Δ × S/O, using Black-Scholes delta)
  - `efficiency`, `eff`: Efficiency percentile, calls only (leverage/CAGR ratio, 0-100 scale)

- **Examples:**
  - `--filter "dte>300"` - Options with more than 300 days to expiry
  - `--filter "dte>10, dte<50"` - Options between 10-50 days (AND operation)
  - `--filter "dte<30 + dte>300"` - Short-term OR long-dated (OR operation)
  - `--filter "sp>5, sp<15"` - Strikes 5-15% above current spot price
  - `--filter "(dte>300 + dte<30), sp>5"` - Complex nested filters
  - `--filter "volume>=100"` - High volume options
  - `--filter "lt_days<=7"` - Options traded within last 7 days
  - `--filter "ar>50"` - Annualized return > 50%
  - `--filter "leverage>10"` - High leverage options (10x or more)
  - `--filter "lev>5, lev<20"` - Moderate leverage options (5x-20x)
  - `--filter "efficiency>80"` - Top 20% most efficient options
  - `--filter "eff>60, dte<60"` - Above-average efficiency with <60 days to expiry

- **Time Values:**
  - DTE-style expressions: `1y` (365 days), `6m` (180 days), `2w` (14 days)
  - Duration expressions: `2d15h`, `30m`, `1d` (converted to hours for duration fields)
  - Examples:
    - `--filter "dte>1y"` - Options with more than 1 year to expiry
    - `--filter "dte>6m"` - Options with more than 6 months to expiry
    - `--filter "lt_days<=7"` - Options traded in the last week

**Named Filter Presets:**

Save frequently used filters for quick reuse. Filters are separate for calls and puts,
stored in `~/.config/grynn_fplot/filters.json`.

```shell
# Save a put filter
fplot --put --save-filter vishal --filter "dte>7, lt_days<2d15h, sp<15, dte<33"

# Save a call filter
fplot --call --save-filter leaps --filter "dte>1y, sp>5"

# Use a saved filter
fplot AAPL --put --filter vishal
fplot AAPL --call --filter leaps

# List all saved filters (shows both calls and puts)
fplot --list-filters

# Delete a saved filter
fplot --put --delete-filter vishal

# Set a default filter (applied when no --filter is given)
fplot --put --default-filter vishal
fplot --call --default-filter leaps

# Clear the default
fplot --put --default-filter none
```

Options data is cached for 1 hour to improve performance and reduce API calls.

## TODO

- fplot --call | fzf lets you select a call; once a call is selected it should be possible to plot a chart for it (yfinance provides price history for option identifiers)
- need more examples of usage with fzf to pick a call
- use grynn_pylib to download options (does it have identifiers that can be used to fetch price history?)
