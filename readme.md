# Display comparative stock price history

## Development

For development, install the package in editable mode with `make dev`

## Installation

`make install` installs fplot using uv tool install making it available across the system.

Still in development, so not yet available on PyPI. Have to use make install instead of `uv tool install grynn_fplot`

## Usage

```shell
fplot <ticker> [--since <date>] [--interval <interval>]
```

Examples:

- `fplot AAPL`
- `fplot AAPL --since 2020`
- `fplot AAPL,TSLA --since "mar 2023"`
