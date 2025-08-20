# Financial Plotting CLI Tool
Financial plotting CLI tool (fplot) is a Python application that provides both a command-line interface and a web interface for plotting stock price data, drawdowns, and financial analysis. Built with Python 3.12+, matplotlib, FastAPI, and managed with uv package manager.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Bootstrap and Setup
- Install uv package manager: `pip install uv`
- Bootstrap the development environment: `make dev`
  - Takes ~3 minutes for fresh setup. NEVER CANCEL. Set timeout to 10+ minutes.
  - Creates virtual environment and installs all dependencies including scipy, matplotlib, pandas
  - Subsequent runs take <1 second due to caching
- Install CLI tool system-wide: `make install`
  - Takes ~3 minutes for fresh install. NEVER CANCEL. Set timeout to 10+ minutes.
  - Makes `fplot` command available globally via uv tool install

### Testing and Quality
- Run tests: `make test` or `uv run pytest`
  - Takes ~6 seconds. Set timeout to 30+ seconds.
  - All tests must pass before committing changes
- Run linter: `make lint` or `uvx ruff check`
  - Takes <1 second. Set timeout to 30+ seconds.
  - Code must pass linting before committing changes
- Clean build artifacts: `make clean`

### Build and Development
- Development setup: `make dev`
  - NEVER CANCEL: Takes up to 3 minutes for fresh setup. Set timeout to 10+ minutes.
  - Downloads and builds many packages including scipy (35MB+), matplotlib, pandas
  - Subsequent runs are nearly instantaneous due to uv caching
- The project has no separate "build" step - it's a Python package installed directly

## Running the Application

### CLI Tool
- Basic usage: `fplot <ticker> [options]`
- Examples:
  - `fplot AAPL` - Plot Apple stock (last 1 year default)
  - `fplot AAPL --since "last 30 days"` - Plot Apple stock for last 30 days
  - `fplot AAPL,TSLA --since "mar 2023"` - Compare multiple tickers
  - `fplot --version` - Show version
  - `fplot --help` - Show help

### Web Interface
- Start web server: `uv run python grynn_fplot/serve.py`
  - Runs on http://0.0.0.0:8000
  - Provides interactive HTML interface with Plotly charts
  - Hot reloads on code changes in development

### Network Requirements
- CLI and web server require internet access to download financial data from Yahoo Finance
- Without internet, commands will fail with DNS resolution errors (expected behavior)
- All core functionality works offline with sample data

## Validation

### Always Test After Making Changes
1. **Run the full test suite**: `make test` - must pass completely
2. **Run the linter**: `make lint` - must pass without issues
3. **Test CLI functionality**:
   - `fplot --version` should show current version
   - `fplot --help` should show usage information
   - If internet is available, test with real ticker: `fplot AAPL --since "last 7 days"`
4. **Test web server**:
   - Start server: `uv run python grynn_fplot/serve.py`
   - Verify http://localhost:8000 loads the HTML interface
   - Check that page contains "Stock Chart" and plotly references
5. **Test core functionality with sample data**:
   - All core functions (normalize_prices, calculate_drawdowns, calculate_cagr, etc.) work correctly
   - Date parsing handles various formats correctly

### Manual Validation Scenarios
- **CLI Workflow**: `fplot --version` → `fplot --help` → verify output is correct
- **Web Workflow**: Start server → verify homepage loads → check HTML contains expected UI elements
- **Date Parsing**: Test with "last 30 days", "YTD", "last 6 months", "2 years ago"

## Common Tasks

### Key Project Structure
```
/home/runner/work/grynn_cli_fplot/grynn_cli_fplot/
├── grynn_fplot/                 # Main package
│   ├── cli.py                   # CLI command implementation
│   ├── core.py                  # Core financial functions
│   ├── serve.py                 # FastAPI web server
│   └── index.html               # Web UI template
├── tests/                       # Test suite
├── Makefile                     # Build automation
├── pyproject.toml               # Package configuration
└── uv.lock                      # Dependency lock file
```

### Dependencies and External Libraries
- **Package Manager**: uv (modern Python package manager)
- **Core Dependencies**: click, matplotlib, pandas, yfinance, scikit-learn
- **Web Dependencies**: fastapi, uvicorn  
- **Dev Dependencies**: pytest, ruff, mypy
- **External Git Dependencies**: 
  - grynn-pylib from https://github.com/Grynn/grynn_pylib.git
  - yfinance from https://github.com/ranaroussi/yfinance.git

### Timing Expectations and Timeouts
- **CRITICAL**: NEVER CANCEL builds or dependency installations - they may take 3+ minutes
- **make dev**: 3 minutes fresh, <1 second cached. Timeout: 10+ minutes.
- **make install**: 3 minutes fresh, <1 second cached. Timeout: 10+ minutes.  
- **make test**: 6 seconds. Timeout: 30+ seconds.
- **make lint**: <1 second. Timeout: 30+ seconds.
- **CLI commands**: <5 seconds (plus network time for data). Timeout: 60+ seconds.
- **Web server startup**: 3 seconds. Timeout: 30+ seconds.

### Key Files to Monitor
- Always check `pyproject.toml` when changing dependencies
- Always check `grynn_fplot/core.py` when modifying financial calculations
- Always check `grynn_fplot/cli.py` when changing CLI behavior
- Always check `tests/test_fplot.py` when adding new functionality

### Development Environment Details
- **Python Version**: 3.12+ required
- **Virtual Environment**: Managed by uv in `.venv/`
- **Package Installation**: Uses `uv tool install` for global CLI access
- **Code Style**: Enforced by ruff linter with 120 character line length
- **Testing**: pytest-based with unittest-style test classes

## Troubleshooting

### Common Issues
- **ModuleNotFoundError**: Run `make dev` to ensure all dependencies are installed
- **DNS/Network Errors**: Expected when internet is limited - test with sample data instead
- **Build timeouts**: Increase timeout values - builds legitimately take 3+ minutes fresh
- **Import errors**: Use `uv run` prefix for all Python commands to use virtual environment

### Build Problems
- Clean and rebuild: `make clean && make dev`
- Check uv version: `uv --version` (should be 0.8+)
- Verify Python version: `python3 --version` (should be 3.12+)

### Testing Without Network
- CLI will show DNS errors but this is expected behavior
- Use core functionality tests with sample data to verify logic
- Web server will start but data endpoints will fail (expected)