# fplot TODO

## ~~Pre-fetch extended historical data for smooth pan/scroll/zoom~~ ✅

Completed in PR #14 — 10yr data pre-fetch with 5min cache, `--since` controls initial view window.

## ~~Speed is the #1 priority~~ ✅

Completed in PR #14 — cached raw yfinance output, instant loads on repeat queries.

## ~~Interactive pan/scroll/zoom on native charts~~ ✅

Completed in PR #14 + follow-up fix — charts now plot ALL pre-fetched data with initial xlim set to `--since` window; panning left/zooming out reveals full history.

## ~~Alfred workflow plugin ([#15](https://github.com/Grynn/grynn_cli_fplot/issues/15))~~ ✅

Completed in PR #16 + #17 — workflow built, packaged as `.alfredworkflow`, added to releases.

---

## Fix Alfred workflow argument quoting ([#18](https://github.com/Grynn/grynn_cli_fplot/issues/18))

- Alfred passes `"$@"` which sends the entire query as a single argument (e.g., `DX-Y.NYB --since 3y` as one string)
- fplot's CLI parser expects separate arguments, so the ticker+flags get treated as a single symbol
- Need to use unquoted `$@` or `eval` to split arguments properly
