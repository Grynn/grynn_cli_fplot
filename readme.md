# Display comparative stock price history

## Install

For development, install the package in editable mode with
`make install`

Still in development, so not yet available on PyPI.

## Usage

```shell
fplot <ticker> [--since <date>] [--interval <interval>]
```

Examples:

- `fplot AAPL`
- `fplot AAPL --since 2020`
- `fplot AAPL,TSLA --since "mar 2023"`
