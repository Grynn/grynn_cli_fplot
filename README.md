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

The options output includes pricing, return metrics, implied leverage, and efficiency:
```
AAPL 225C 35DTE ($5.25, 18.5%, 19.0x, eff:45)
AAPL 230C 35DTE ($3.10, 25.2%, 32.3x, eff:78)
AAPL 235C 35DTE ($1.85, 35.1%, 54.1x, eff:92)
```

Format: `TICKER STRIKE[C|P] DAYS_TO_EXPIRY (price, return_metric, leverage, eff:percentile)`
- **Price**: Uses **ask price** (what you'd pay to buy) for accurate buyer calculations. Falls back to lastPrice if ask unavailable.
- For calls: return_metric is CAGR to breakeven
- For puts: return_metric is annualized return
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
  - `price`: Option price (ask price for buyers)
  - `bid`: Bid price (what you'd receive if selling)
  - `ask`: Ask price (what you'd pay if buying)
  - `return`, `ret`, `ar`: Return metric (CAGR for calls, annualized return for puts) - all aliases work
  - `strike_pct`, `sp`: Strike percentage above/below spot (positive = above spot, negative = below spot)
  - `lt_days`: Days since last trade (useful for filtering stale options)
  - `leverage`, `lev`: Implied leverage (Ω = Δ × S/O, using Black-Scholes delta)
  - `efficiency`, `eff`: Efficiency percentile (leverage/CAGR ratio, 0-100 scale)

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

Options data is cached for 1 hour to improve performance and reduce API calls.
