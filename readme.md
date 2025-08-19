# Display comparative stock price history

## Development

For development, install the package in editable mode with `make dev`

## Installation

`make install` installs fplot using uv tool install making it available across the system.

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
fplot <ticker> --call    # List all available call options
fplot <ticker> --put     # List all available put options
```

Examples:

- `fplot AAPL --call`
- `fplot TSLA --put`

The options output is formatted for easy filtering with tools like `fzf`:
```
AAPL 95C 10DTE
AAPL 100C 10DTE
AAPL 105C 10DTE
```

Where the format is: `TICKER STRIKE[C|P] DAYS_TO_EXPIRY`

Options data is cached for 1 hour to improve performance and reduce API calls.
