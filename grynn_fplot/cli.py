# ruff: noqa: E402

import importlib.metadata
import importlib
import importlib.util
import os
import sys
import tempfile

import click
import matplotlib


def _choose_matplotlib_backend() -> str | None:
    """Choose an interactive backend when the environment supports one.

    Respect an explicit MPLBACKEND, prefer modern GUI backends for CLI use,
    and fall back to Agg in clearly headless Linux environments.
    """
    if os.environ.get("MPLBACKEND"):
        return None

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return "Agg"

    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return "Agg"

    candidates: list[str] = []

    if any(importlib.util.find_spec(module) for module in ("PyQt6", "PySide6", "PyQt5", "PySide2")):
        candidates.append("QtAgg")

    if sys.platform == "darwin":
        candidates.append("macosx")

    try:
        import tkinter  # noqa: F401

        candidates.append("TkAgg")
    except Exception:
        pass

    backend_modules = {
        "QtAgg": "matplotlib.backends.backend_qtagg",
        "TkAgg": "matplotlib.backends.backend_tkagg",
        "macosx": "matplotlib.backends.backend_macosx",
    }

    for backend in candidates:
        module_name = backend_modules.get(backend)
        if not module_name:
            continue
        try:
            importlib.import_module(module_name)
            return backend
        except Exception:
            continue

    return None


def _configure_matplotlib_backend() -> None:
    backend = _choose_matplotlib_backend()
    if backend:
        matplotlib.use(backend, force=True)


_configure_matplotlib_backend()

import matplotlib.pyplot as plt
import mplcursors
import mplfinance as mpf
import numpy as np
from grynn_pylib.finance.timeseries import rolling_cagr
from loguru import logger
from tabulate import tabulate

from grynn_fplot.core import (
    calculate_area_under_curve,
    calculate_cagr,
    calculate_drawdowns,
    download_ohlcv_data,
    download_ticker_data,
    format_options_for_display,
    normalize_prices,
    parse_start_date,
)


def _attach_drag_pan(fig, axes, clamp_min=None, clamp_max=None) -> None:
    """Enable left-click drag panning across a shared x-axis."""
    pan_state = {"active": False, "x": None, "xlim": None}

    def _clamp_xlim(left, right):
        if clamp_min is None or clamp_max is None:
            return left, right

        width = right - left
        if width <= 0:
            return clamp_min, clamp_max

        if width >= (clamp_max - clamp_min):
            return clamp_min, clamp_max

        if left < clamp_min:
            right += clamp_min - left
            left = clamp_min
        if right > clamp_max:
            left -= right - clamp_max
            right = clamp_max
        return left, right

    def _on_press(event):
        if event.button != 1 or event.inaxes not in axes or event.xdata is None:
            return
        pan_state["active"] = True
        pan_state["x"] = event.xdata
        pan_state["xlim"] = axes[0].get_xlim()

    def _on_motion(event):
        if not pan_state["active"] or event.xdata is None or pan_state["xlim"] is None or pan_state["x"] is None:
            return

        dx = event.xdata - pan_state["x"]
        left, right = pan_state["xlim"]
        new_left, new_right = _clamp_xlim(left - dx, right - dx)
        for ax in axes:
            ax.set_xlim(new_left, new_right)
        fig.canvas.draw_idle()

    def _on_release(event):
        pan_state["active"] = False
        pan_state["x"] = None
        pan_state["xlim"] = None

    fig.canvas.mpl_connect("button_press_event", _on_press)
    fig.canvas.mpl_connect("motion_notify_event", _on_motion)
    fig.canvas.mpl_connect("button_release_event", _on_release)


def _visible_mask_from_xlim(x_values, left, right):
    """Return a row mask for data points visible within a matplotlib x-axis range."""
    if len(x_values) == 0:
        return np.array([], dtype=bool)

    left, right = sorted((left, right))
    mask = (x_values >= left) & (x_values <= right)
    if mask.any():
        return mask

    # Very narrow zooms can fall between observations. Use the nearest point so
    # normalization still has a stable base instead of leaving the chart blank.
    nearest = int(np.clip(np.searchsorted(x_values, left), 0, len(x_values) - 1))
    mask[nearest] = True
    return mask


def _normalize_frame_to_visible_window(df, visible_mask, start=100):
    """Normalize full data to the first valid observation in the visible window.

    Drawdowns are intentionally reset to the visible window, matching what the
    user is currently evaluating after a pan or zoom.
    """
    visible = df.iloc[visible_mask]
    normalized = df.copy().astype(float) * np.nan
    drawdown = normalized.copy()

    if visible.empty:
        return normalized, drawdown

    base = visible.apply(lambda series: series.dropna().iloc[0] if series.notna().any() else np.nan)
    normalized = df.div(base).mul(start)

    visible_normalized = normalized.loc[visible.index]
    drawdown.loc[visible.index] = calculate_drawdowns(visible_normalized)
    return normalized, drawdown


def _set_padded_ylim(ax, values, *, zero_top=False) -> None:
    """Set a compact y-axis around finite visible values."""
    finite_values = np.asarray(values, dtype=float)
    finite_values = finite_values[np.isfinite(finite_values)]
    if finite_values.size == 0:
        return

    y_min = float(np.min(finite_values))
    y_max = float(np.max(finite_values))

    if zero_top:
        y_min = min(y_min, 0.0)
        pad = max(abs(y_min) * 0.05, 0.01)
        ax.set_ylim(y_min - pad, 0.0)
        return

    if y_max == y_min:
        pad = max(abs(y_min) * 0.05, 1.0)
    else:
        pad = (y_max - y_min) * 0.05
    ax.set_ylim(y_min - pad, y_max + pad)


def _set_candlestick_visible_ylim(ax, df, moving_averages=()) -> None:
    """Fit the price axis to candles and overlays inside its visible x-range."""
    left, right = sorted(ax.get_xlim())
    start = max(int(np.floor(left)), 0)
    stop = min(int(np.ceil(right)) + 1, len(df))
    if start >= stop:
        nearest = int(np.clip(round(left), 0, len(df) - 1))
        start, stop = nearest, nearest + 1

    price_columns = [column for column in ("Open", "High", "Low", "Close") if column in df.columns]
    visible_values = [df.iloc[start:stop][price_columns].to_numpy().ravel()]
    visible_values.extend(series.iloc[start:stop].to_numpy() for series in moving_averages)
    _set_padded_ylim(ax, np.concatenate(visible_values))


try:
    # if __package__ is None and __name__ == "__main__" this is being run from vscode interactive
    __version__ = importlib.metadata.version(__package__ or __name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = f"unknown (__name__: {__name__})"


@click.command()
@click.option("--since", type=str, default=None, help="Start date for data (e.g., '1y', '6m', '2023-01-01')")
@click.option("--interval", type=str, default="1d", help="Data interval (1d, 1wk, 1mo)")
@click.argument("ticker", type=str, nargs=-1, required=False)
@click.option("--version", "-v", is_flag=True, help="Show version and exit")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--call", is_flag=True, help="List all available call options for the ticker")
@click.option("--put", is_flag=True, help="List all available put options for the ticker")
@click.option(
    "--max",
    "max_expiry",
    type=str,
    default="6m",
    help="Maximum expiry time for options (e.g., '3m', '6m', '1y'). Default: 6m",
)
@click.option("--min-dte", type=str, default=None, help="Minimum days to expiry (e.g., '30', '1y', '6m', '2w')")
@click.option("--all", "show_all", is_flag=True, help="Show all available expiries (overrides --max)")
@click.option(
    "--filter",
    "filter_expr",
    type=str,
    default=None,
    help="Filter expression (e.g., 'dte>300', 'dte>10, dte<15', 'dte>300 + strike<100')",
)
@click.option("--filter-help", is_flag=True, help="Show help for filter expressions and exit")
@click.option("--save-filter", type=str, default=None, help="Save --filter expression with this name for reuse")
@click.option("--list-filters", is_flag=True, help="List all saved filter presets")
@click.option("--delete-filter", type=str, default=None, help="Delete a saved filter preset by name")
@click.option("--default-filter", type=str, default=None, help="Set a saved filter as default (use 'none' to clear)")
@click.option("--web", "-w", is_flag=True, help="Launch interactive web interface")
@click.option("--port", type=int, default=8000, help="Port for web interface")
@click.option("--host", type=str, default="127.0.0.1", help="Host for web interface")
@click.option("--no-browser", is_flag=True, help="Don't automatically open browser")
def display_plot(
    ticker,
    since,
    interval,
    version,
    debug,
    call,
    put,
    max_expiry,
    min_dte,
    show_all,
    filter_expr,
    filter_help,
    save_filter,
    list_filters,
    delete_filter,
    default_filter,
    web,
    port,
    host,
    no_browser,
):
    """Generate a plot of the given ticker(s) or list options contracts.

    When --call or --put flags are used, lists available options contracts
    in a format suitable for filtering with tools like fzf.

    Output format:
    - Calls: TICKER STRIKE_C DTE (price, CAGR, leverage, eff:percentile)
    - Puts: table with expiry, strike, breakeven, lt_days, AR (bid/ask/last)

    Return metrics:
    - Calls: CAGR to breakeven
    - Puts: AR = premium / capital-at-risk, annualized (capital-at-risk = strike - premium)

    Examples:
    \b
    # Single ticker
    fplot AAPL

    # Multiple tickers (space-separated)
    fplot AAPL TSLA MSFT

    # Comma-separated tickers
    fplot AAPL,TSLA

    # Division operations
    fplot AAPL/XLK

    # Mixed inputs
    fplot AAPL AAPL/XLK TW.L

    # Quoted strings with commas
    fplot "AAPL, TSLA"

    # List all AAPL call options (default: 6 months max)
    fplot AAPL --call

    # List TSLA put options with 3 month max expiry
    fplot TSLA --put --max 3m

    # List all available call options (no expiry limit)
    fplot AAPL --call --all

    # Interactive filtering with fzf
    fplot AAPL --call | fzf
    """
    logger.remove()  # Remove default handlers
    logger.add(sys.stdout, level="DEBUG" if debug else "WARNING")

    if debug:
        logger.debug("Debug mode enabled")

    # Process arguments
    if version:
        print(f"fplot {__version__}")
        return

    # Show filter help if requested
    if filter_help:
        from grynn_fplot.filter_parser import get_filter_help

        print(get_filter_help())
        return

    # Handle named filter management commands
    if list_filters:
        from grynn_fplot.filter_store import load_filters, get_default_filter

        has_any = False
        for otype in ("calls", "puts"):
            filters = load_filters(otype)
            default_name = get_default_filter(otype)
            if filters:
                has_any = True
                click.echo(f"{otype}:")
                for name, expr in sorted(filters.items()):
                    marker = " (default)" if name == default_name else ""
                    click.echo(f"  {name}: {expr}{marker}")
        if not has_any:
            click.echo('No saved filters. Save one with: fplot --call --save-filter NAME --filter "EXPRESSION"')
        return

    # Determine option type for filter management commands
    filter_mgmt_type = "calls" if call else "puts" if put else None

    if delete_filter:
        if not filter_mgmt_type:
            click.echo("Error: --delete-filter requires --call or --put to specify which type.")
            return
        from grynn_fplot.filter_store import delete_filter as do_delete

        if do_delete(delete_filter, filter_mgmt_type):
            click.echo(f"Deleted {filter_mgmt_type} filter '{delete_filter}'.")
        else:
            click.echo(f"Filter '{delete_filter}' not found in {filter_mgmt_type}.")
        return

    if save_filter:
        if not filter_mgmt_type:
            click.echo("Error: --save-filter requires --call or --put to specify which type.")
            return
        if not filter_expr:
            click.echo("Error: --save-filter requires --filter to specify the expression to save.")
            return
        try:
            from grynn_fplot.filter_store import save_filter as do_save

            do_save(save_filter, filter_expr, filter_mgmt_type)
            click.echo(f"Saved {filter_mgmt_type} filter '{save_filter}': {filter_expr}")
        except (ValueError, Exception) as e:
            click.echo(f"Error: {e}")
        return

    if default_filter is not None:
        if not filter_mgmt_type:
            click.echo("Error: --default-filter requires --call or --put to specify which type.")
            return
        from grynn_fplot.filter_store import set_default_filter

        try:
            if default_filter.lower() == "none":
                set_default_filter(None, filter_mgmt_type)
                click.echo(f"Cleared default {filter_mgmt_type} filter.")
            else:
                set_default_filter(default_filter, filter_mgmt_type)
                click.echo(f"Default {filter_mgmt_type} filter set to '{default_filter}'.")
        except ValueError as e:
            click.echo(f"Error: {e}")
        return

    # Convert ticker tuple to list (Click's variadic arguments return a tuple)
    ticker_list = list(ticker) if ticker else []
    # Launch web interface if --web flag is used
    if web:
        # For web interface, join tickers back into a string
        ticker_str = ",".join(ticker_list) if ticker_list else None
        launch_web_interface(ticker_str, since, interval, port, host, no_browser, debug)
        return

    # CLI mode - require ticker
    if not ticker_list:
        click.echo("Error: Missing argument 'TICKER'. Please provide ticker symbol(s).")
        click.echo("Examples:")
        click.echo("  fplot AAPL")
        click.echo("  fplot AAPL TSLA")
        click.echo("  fplot AAPL,TSLA")
        click.echo("  fplot AAPL/XLK")
        click.echo('  fplot "AAPL, TSLA"')
        click.echo("Hint: Use --web or -w to launch the interactive web interface.")
        return

    # Resolve filter: named preset, inline expression, or default
    parsed_filter = None
    effective_filter_expr = filter_expr
    active_option_type = "calls" if call else "puts" if put else None
    if not effective_filter_expr and active_option_type:
        # Apply default filter if no explicit filter provided for options
        from grynn_fplot.filter_store import get_default_filter, resolve_filter

        default_name = get_default_filter(active_option_type)
        if default_name:
            effective_filter_expr = resolve_filter(default_name, active_option_type)
            if debug:
                logger.debug(f"Using default {active_option_type} filter '{default_name}': {effective_filter_expr}")
    elif effective_filter_expr and active_option_type:
        from grynn_fplot.filter_store import resolve_filter

        resolved = resolve_filter(effective_filter_expr, active_option_type)
        if resolved != effective_filter_expr:
            if debug:
                logger.debug(f"Resolved filter '{effective_filter_expr}' to: {resolved}")
            effective_filter_expr = resolved

    if effective_filter_expr:
        try:
            from grynn_fplot.filter_parser import parse_filter, FilterParseError

            parsed_filter = parse_filter(effective_filter_expr)
            if debug:
                logger.debug(f"Parsed filter: {parsed_filter}")
        except FilterParseError as e:
            click.echo(f"Error: Invalid filter expression: {e}")
            click.echo("Filter syntax: Use comma (,) for AND, plus (+) for OR")
            click.echo("Examples: 'dte>300', 'dte>10, dte<15', 'dte>300 + strike<100'")
            return

    # Parse min_dte if provided (supports formats like '30', '1y', '6m', '2w')
    parsed_min_dte = None
    if min_dte:
        try:
            # Try to parse as integer first
            parsed_min_dte = int(min_dte)
        except ValueError:
            # Try to parse as time expression (1y, 6m, 2w, 30d)
            try:
                from grynn_fplot.filter_parser import parse_dte_value, FilterParseError

                parsed_min_dte = parse_dte_value(min_dte)
                if debug:
                    logger.debug(f"Parsed min_dte '{min_dte}' to {parsed_min_dte} days")
            except FilterParseError:
                click.echo(f"Error: Invalid min-dte value: '{min_dte}'")
                click.echo("Expected format: integer days or time expression (e.g., '30', '1y', '6m', '2w')")
                return

    # When --filter or --min-dte is specified, don't use default values for --max unless explicitly set or --all is used
    # This allows filters to work on all options without artificial date limits
    use_show_all = show_all
    use_max_expiry = max_expiry
    if (effective_filter_expr or parsed_min_dte) and not show_all:
        # Check if max_expiry was explicitly set by the user (not just the default)
        # Since we can't easily detect if a default was used, we'll treat filter/min_dte as implying --all behavior
        # unless max is explicitly different from default or --all is already set
        use_show_all = True
        use_max_expiry = None  # Will be ignored when show_all is True

    # Handle options listing
    if call:
        # For options, use the first ticker only (options only work with single ticker)
        ticker_for_options = ticker_list[0] if ticker_list else ""
        options_list = format_options_for_display(
            ticker_for_options,
            "calls",
            max_expiry=use_max_expiry,
            min_dte=parsed_min_dte,
            show_all=use_show_all,
            filter_ast=parsed_filter,
        )
        if not options_list:
            click.echo(f"No call options found for {ticker_for_options.upper()}")
            return

        for option in options_list:
            print(option)
        return

    if put:
        # For options, use the first ticker only (options only work with single ticker)
        ticker_for_options = ticker_list[0] if ticker_list else ""
        options_list = format_options_for_display(
            ticker_for_options,
            "puts",
            max_expiry=use_max_expiry,
            min_dte=parsed_min_dte,
            show_all=use_show_all,
            filter_ast=parsed_filter,
        )
        if not options_list:
            click.echo(f"No put options found for {ticker_for_options.upper()}")
            return

        for option in options_list:
            print(option)
        return

    # Continue with original CLI plotting logic
    display_cli_plot(ticker_list, since, interval, debug)


def launch_web_interface(ticker, since, interval, port, host, no_browser, debug):
    """Launch the web interface using uvicorn"""
    import subprocess
    import time
    import threading

    try:
        # Import uvicorn here to avoid import issues
        import uvicorn
        from grynn_fplot.serve import app

        # Build the URL
        url = f"http://{host}:{port}"
        if ticker:
            # If ticker is provided but no since parameter, use 5y for preloading
            if since is None:
                url += f"?ticker={ticker}&preload=5y"
            else:
                url += f"?ticker={ticker}&since={since}"

        print("🚀 Starting fplot web interface...")
        print(f"📊 Server will be available at: {url}")

        if ticker:
            print(f"📈 Pre-loading data for: {ticker}")

        # Start browser immediately if requested - don't wait for server
        browser_opened = False
        if not no_browser:

            def open_browser_early():
                nonlocal browser_opened
                # Try to open browser with a shorter delay
                time.sleep(0.5)
                try:
                    # Use npx open-in-browser for better cross-platform support
                    subprocess.run(["npx", "open-in-browser", url], check=False, capture_output=True, timeout=10)
                    browser_opened = True
                    print(f"🌐 Opening {url} in your default browser...")
                except subprocess.TimeoutExpired:
                    print("⚠️  Browser opening timed out")
                    print(f"📱 Please manually open: {url}")
                except subprocess.CalledProcessError as e:
                    print(f"⚠️  Browser opening failed: {e}")
                    print(f"📱 Please manually open: {url}")
                except FileNotFoundError:
                    print("⚠️  npx not found, trying fallback...")
                    # Fallback to Python webbrowser
                    try:
                        import webbrowser

                        webbrowser.open(url)
                        browser_opened = True
                        print(f"🌐 Opened {url} using fallback method")
                    except Exception as fallback_error:
                        print(f"⚠️  Fallback browser opening failed: {fallback_error}")
                        print(f"📱 Please manually open: {url}")
                except Exception as e:
                    print(f"⚠️  Could not open browser automatically: {e}")
                    print(f"📱 Please manually open: {url}")

            # Start browser opening in parallel
            threading.Thread(target=open_browser_early, daemon=True).start()

        # Configure uvicorn logging
        log_level = "debug" if debug else "info"

        print("⚡ Starting server...")
        if not no_browser and not browser_opened:
            print("🌐 Browser will open automatically once server is ready...")
        print("🛑 Press Ctrl+C to stop the server")

        # Create uvicorn config for faster startup
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level=log_level,
            access_log=debug,
            reload=False,  # Disable reload for faster startup
            workers=1,  # Single worker for CLI mode
            loop="asyncio",  # Use asyncio for better performance
        )

        # Run the server
        server = uvicorn.Server(config)
        server.run()

    except ImportError as e:
        print(f"❌ Error: Required web dependencies not available: {e}")
        print("💡 Make sure FastAPI and uvicorn are installed")
        print("🔧 Try: uv install fastapi uvicorn")
        return
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
        return
    except Exception as e:
        print(f"❌ Error starting web interface: {e}")
        return


def _add_scroll_zoom(fig, axes, date_index):
    """Add mouse-wheel zoom and date-aware x-axis ticks to a chart.

    Args:
        fig: matplotlib Figure
        axes: list of Axes (mplfinance returns multiple: price, volume, etc.)
        date_index: pandas DatetimeIndex for the data
    """
    import matplotlib.ticker as mticker

    # Custom formatter: map integer x-position → date string
    dates = date_index.to_pydatetime() if hasattr(date_index, "to_pydatetime") else list(date_index)

    def _format_date(x, pos=None):
        ix = int(round(x))
        if 0 <= ix < len(dates):
            d = dates[ix]
            return d.strftime("%Y-%m-%d")
        return ""

    for ax in axes:
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(_format_date))

    def _on_scroll(event):
        if event.inaxes is None:
            return
        ax = axes[0]  # primary axis controls shared x
        cur_xlim = ax.get_xlim()
        xdata = event.xdata
        if xdata is None:
            xdata = (cur_xlim[0] + cur_xlim[1]) / 2
        # Zoom factor: scroll up → zoom in, scroll down → zoom out
        scale = 0.8 if event.button == "up" else 1.25
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale
        # Keep the point under the cursor stationary
        rel = (xdata - cur_xlim[0]) / (cur_xlim[1] - cur_xlim[0])
        new_left = xdata - new_width * rel
        new_right = xdata + new_width * (1 - rel)
        # Clamp to data range
        new_left = max(new_left, 0)
        new_right = min(new_right, len(dates) - 1)
        for ax in axes:
            ax.set_xlim(new_left, new_right)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("scroll_event", _on_scroll)


def display_candlestick_plot(ticker, since, interval, debug):
    """Display candlestick plot with volume and SMAs for a single ticker

    Pre-fetches 10 years of data for smooth pan/scroll/zoom.
    The 'since' parameter controls the initial view window.
    """
    import pandas as pd

    requested_since = parse_start_date(since)

    # Download full dataset for computing SMAs and enabling pan/zoom
    df = download_ohlcv_data(ticker, None, interval)
    if df.empty:
        print(f"No data found for {ticker}.")
        return

    # Find the integer index position for the initial view start
    view_start_idx = 0
    if requested_since is not None:
        filter_since = requested_since
        index_tz = getattr(df.index, "tz", None)
        if index_tz is not None and requested_since.tzinfo is None:
            filter_since = requested_since.replace(tzinfo=index_tz)
        mask = df.index >= filter_since - pd.Timedelta(seconds=1)
        positions = np.where(mask)[0]
        if len(positions) > 0:
            view_start_idx = positions[0]

    view_count = len(df) - view_start_idx

    sma_50 = df["Close"].rolling(window=50).mean()
    sma_200 = df["Close"].rolling(window=200).mean()

    print(
        f"Generating candlestick plot for {ticker} since "
        f"{requested_since.date() if requested_since else 'max'}. Interval: {interval}"
    )
    print(f"📊 Loaded {len(df)} data points (up to 10 years cached)")
    if view_start_idx > 0:
        print(f"🔍 Initial view: {view_count} data points — scroll to zoom, drag to pan")

    if debug:
        print(f"Data for {ticker}:")
        print(f"Full dataset: {len(df)} rows, View start index: {view_start_idx}")
        print(df.head())
        temp_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        df.to_csv(temp_file.name)
        print(f"Data saved to temporary file: {temp_file.name}")

    # Create additional plots list for SMAs
    add_plots = []
    if not sma_50.isna().all():
        add_plots.append(mpf.make_addplot(sma_50, color="orange", width=1.5, label="50-day SMA"))
    if not sma_200.isna().all():
        add_plots.append(mpf.make_addplot(sma_200, color="red", width=1.5, label="200-day SMA"))

    # Configure mplfinance style
    mc = mpf.make_marketcolors(
        up="green",
        down="red",
        wick={"up": "green", "down": "red"},
        edge={"up": "green", "down": "red"},
        volume={"up": "green", "down": "red"},
    )
    s = mpf.make_mpf_style(marketcolors=mc, gridstyle=":", y_on_right=False)

    # Plot ALL data with mplfinance
    fig, axes = mpf.plot(
        df,
        type="candle",
        style=s,
        volume=True,
        addplot=add_plots if add_plots else None,
        title=f"{ticker} - Candlestick Chart",
        ylabel="Price",
        ylabel_lower="Volume",
        figsize=(16, 10),
        xrotation=15,
        returnfig=True,
        warn_too_much_data=10000,
    )

    # Set initial view to --since range using integer x-positions
    if view_start_idx > 0:
        for ax in axes:
            ax.set_xlim(view_start_idx, len(df) - 1)

    moving_averages = tuple(series for series in (sma_50, sma_200) if not series.isna().all())

    def _autoscale_visible_prices(ax):
        _set_candlestick_visible_ylim(ax, df, moving_averages)

    axes[0].callbacks.connect("xlim_changed", _autoscale_visible_prices)
    _autoscale_visible_prices(axes[0])

    # Add scroll-zoom and date tick formatting
    _add_scroll_zoom(fig, axes, df.index)
    _attach_drag_pan(fig, axes, clamp_min=0, clamp_max=len(df) - 1)

    # Add legend
    from matplotlib.lines import Line2D

    legend_elements = [
        Line2D([0], [0], color="green", lw=2, label="Up Day"),
        Line2D([0], [0], color="red", lw=2, label="Down Day"),
    ]
    if not sma_50.isna().all():
        legend_elements.append(Line2D([0], [0], color="orange", lw=1.5, label="50-day SMA"))
    if not sma_200.isna().all():
        legend_elements.append(Line2D([0], [0], color="red", lw=1.5, label="200-day SMA"))
    axes[0].legend(handles=legend_elements, loc="best")

    print("💡 Scroll to zoom, drag to pan, Home button to reset view")

    plt.show()


def display_cli_plot(ticker, since, interval, debug):
    """Display plot using matplotlib (original CLI functionality)

    Pre-fetches 10 years of data for smooth pan/scroll/zoom.
    The 'since' parameter controls the initial view window.
    """
    from grynn_fplot.core import parse_ticker_input

    # Parse ticker input to understand what we're dealing with
    parsed_tickers = parse_ticker_input(ticker)

    # Check if this is a single ticker scenario (should use candlestick)
    # Single ticker means:
    # 1. No division operators in any ticker
    # 2. Exactly one ticker provided (not counting SPY which is auto-added)
    has_division = any("/" in t for t in parsed_tickers)
    ticker_count = len(parsed_tickers)

    # Route to candlestick chart for single ticker without division
    if not has_division and ticker_count == 1:
        display_candlestick_plot(parsed_tickers[0], since, interval, debug)
        return

    # Otherwise, continue with existing line chart logic for multi-ticker or division
    since_parsed = parse_start_date(since)

    # Download ALL data (pass None) so panning/zooming reveals full history
    df_all = download_ticker_data(ticker, None, interval)
    if df_all.empty:
        print(f"No data found for the given tickers({ticker}).")
        return

    # Determine initial view window
    import pandas as pd

    initial_view_start = None
    if since_parsed is not None:
        filter_since = since_parsed
        index_tz = getattr(df_all.index, "tz", None)
        if index_tz is not None and since_parsed.tzinfo is None:
            filter_since = since_parsed.replace(tzinfo=index_tz)
        df_view = df_all[df_all.index >= filter_since - pd.Timedelta(seconds=1)]
        if not df_view.empty:
            initial_view_start = df_view.index[0]
        # Use the view window for metrics calculation
        df = df_view if not df_view.empty else df_all
    else:
        df = df_all

    tickers = df_all.columns.tolist()
    print(
        f"Generating plot for {', '.join(tickers)} since {since_parsed.date() if since_parsed else 'max'}. Interval: {interval}"
    )
    print(f"📊 Loaded {len(df_all)} data points (up to 10 years cached)")
    if initial_view_start is not None:
        print(f"🔍 Initial view: {len(df)} data points — pan left or zoom out to see full history")

    if debug:
        print(f"Data for {', '.join(tickers)}:")
        print(df.head())
        temp_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        df.to_csv(temp_file.name)
        print(f"Data saved to temporary file: {temp_file.name}")

    # Process data

    # Handle edge case, where last row has data for only some tickers
    # (if a ticker is delisted or using different exchanges with different timezones/trading days/calendars)
    # ONLY check last row for now
    last_row_has_missing_data = df.iloc[-1].isna().any()
    if last_row_has_missing_data:
        click.echo("Last row has missing data for some tickers. Dropping the row.")
        click.echo(tabulate(df.iloc[[-1]], headers="keys", tablefmt="pretty", showindex=False))
        df = df.iloc[:-1]  # drop the last row (this helps with plotting)

    # Also clean df_all the same way
    if df_all.iloc[-1].isna().any():
        df_all = df_all.iloc[:-1]

    # Align comparison: drop rows before the first date where all tickers have data,
    # so late-listed tickers don't break the common base.
    if df_all.shape[1] > 1:
        first_common = df_all.dropna(how="any").index.min()
        if pd.notna(first_common):
            df_all = df_all.loc[first_common:]
            df = df.loc[df.index >= first_common]
            if initial_view_start is not None and initial_view_start < first_common:
                initial_view_start = first_common

    # Metrics are computed on the view window (df)
    df_normalized = normalize_prices(df)
    df_dd = calculate_drawdowns(df_normalized)
    df_auc = calculate_area_under_curve(df_dd)
    df_days = (df.index[-1] - df.index[0]).days

    # Display AUC analysis in CLI
    print("\n=== Drawdown Area Under Curve Analysis ===")
    print(tabulate(df_auc, headers="keys", tablefmt="pretty", showindex=False))
    print("Higher values indicate greater drawdowns over time.\n")

    # Calculate and display rolling, median 1-year return if time period >= 1.5 years
    if df_days >= int(365.25 * 1.5):
        df_rolling_cagr = rolling_cagr(df, years=1).median()
        print("\n=== Rolling Median 1 yr Return ===")
        print(df_rolling_cagr.to_string(float_format="{:.2%}".format))

    # Calculate and display rolling, median 3-year return if time period >= 3.5 years
    if df_days >= int(365.25 * 3.5):
        df_rolling_cagr = rolling_cagr(df, years=3).median()
        print("\n=== Rolling Median 3 yr Return ===")
        print(df_rolling_cagr.to_string(float_format="{:.2%}".format))

    # Calculate and display CAGR if time period >= 1 year
    if df_days >= 365:
        cagr_df = calculate_cagr(df_normalized)
        print("\n=== Compound Annual Growth Rate (CAGR) ===")
        print(tabulate(cagr_df, headers="keys", tablefmt="pretty", showindex=False, floatfmt=".2%"))
        print(f"CAGR represents annualized return over the period {df.index[0]} to {df.index[-1]}, {df_days} days.\n")

    # Prepare for plotting — plot ALL data for pan/zoom, set xlim for initial view
    import matplotlib.dates as mdates
    from matplotlib.widgets import Button, RangeSlider

    auc_values = dict(zip(df_auc["Ticker"], df_auc["AUC"]))
    x_values = mdates.date2num(df_all.index.to_pydatetime())
    data_min = float(x_values[0])
    data_max = float(x_values[-1])
    initial_left = mdates.date2num(initial_view_start) if initial_view_start is not None else data_min
    initial_right = data_max
    initial_visible_mask = _visible_mask_from_xlim(x_values, initial_left, initial_right)
    df_all_normalized, df_all_dd = _normalize_frame_to_visible_window(df_all, initial_visible_mask)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(16, 12), sharex=True, gridspec_kw={"height_ratios": [3, 2], "hspace": 0.3}
    )
    fig.subplots_adjust(bottom=0.22)

    # Generate colors for each ticker
    color_map = plt.get_cmap("tab10")
    color_iter = iter(color_map.colors)
    colors = [next(color_iter) if t != "SPY" else "darkgrey" for t in tickers]
    ticker_colors = dict(zip(tickers, colors))
    price_lines = {}
    drawdown_lines = {}
    drawdown_fills = []

    # Plot normalized prices (full history)
    for i, ticker_name in enumerate(tickers):
        label = f"{ticker_name} - AUC: {auc_values[ticker_name]:.2f}"
        # Add CAGR to label if applicable
        if (df_days >= 365) and ticker_name in cagr_df["Ticker"].values:
            cagr_value = cagr_df.loc[cagr_df["Ticker"] == ticker_name, "CAGR"].values[0]
            label += f" - CAGR: {cagr_value:.2%}"

        (price_line,) = ax1.plot(df_all_normalized.index, df_all_normalized[ticker_name], label=label, color=colors[i])
        price_lines[ticker_name] = price_line

    ax1.set_title(f"{', '.join(tickers)} Price")
    ax1.set_ylabel("Normalized Price")
    ax1.legend(loc="best")

    # Plot drawdowns (full history)
    for i, ticker_name in enumerate(tickers):
        (drawdown_line,) = ax2.plot(
            df_all_dd.index,
            df_all_dd[ticker_name],
            label=f"{ticker_name} - AUC: {auc_values[ticker_name]:.2f}",
            color=colors[i],
        )
        drawdown_lines[ticker_name] = drawdown_line
        drawdown_fills.append(ax2.fill_between(df_all_dd.index, df_all_dd[ticker_name], alpha=0.5, color=colors[i]))

    ax2.set_title(f"{', '.join(tickers)} Drawdowns")
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel(f"{interval} intervals")
    ax2.legend(loc="best")

    price_annotations = {
        ticker_name: ax1.annotate(
            "",
            xy=(df_all.index[-1], 100),
            xytext=(5, 0),
            textcoords="offset points",
            color=ticker_colors[ticker_name],
        )
        for ticker_name in tickers
    }

    slider_ax = fig.add_axes([0.12, 0.09, 0.76, 0.03])
    view_slider = RangeSlider(
        slider_ax, "View", data_min, data_max, valinit=(initial_left, initial_right), valfmt="%1.0f"
    )
    view_slider.valtext.set_visible(False)
    slider_ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    view_range_text = slider_ax.text(0.5, 1.25, "", transform=slider_ax.transAxes, ha="center", va="bottom", fontsize=9)
    range_buttons = []

    update_state = {"syncing_slider": False, "skip_xlim_callback": False, "updating": False}

    def _format_num_date(value):
        return mdates.num2date(value).strftime("%Y-%m-%d")

    def _left_for_duration(right, label):
        right_dt = mdates.num2date(right).replace(tzinfo=None)
        amount = int(label[:-1])
        unit = label[-1]

        if unit == "d":
            left_dt = right_dt - pd.Timedelta(days=amount)
        elif unit == "m":
            left_dt = right_dt - pd.DateOffset(months=amount)
        elif unit == "y":
            left_dt = right_dt - pd.DateOffset(years=amount)
        else:
            return data_min

        return mdates.date2num(pd.Timestamp(left_dt).to_pydatetime())

    def _clamp_visible_window(left, right):
        left, right = sorted((left, right))
        width = right - left
        full_width = data_max - data_min

        if width <= 0 or width >= full_width:
            return data_min, data_max

        if left < data_min:
            right += data_min - left
            left = data_min
        if right > data_max:
            left -= right - data_max
            right = data_max
        return max(data_min, left), min(data_max, right)

    def _update_price_annotations(normalized_frame, visible_mask):
        visible_positions = np.flatnonzero(visible_mask)
        for ticker_name, annotation in price_annotations.items():
            visible_series = normalized_frame[ticker_name].iloc[visible_positions].dropna()
            if visible_series.empty:
                annotation.set_visible(False)
                continue

            last_x = visible_series.index[-1]
            last_y = float(visible_series.iloc[-1])
            annotation.xy = (last_x, last_y)
            annotation.set_text(f"{ticker_name}: {last_y - 100:.2f}%")
            annotation.set_visible(True)

    def _update_visible_legends(normalized_frame, drawdown_frame, visible_positions):
        visible_drawdown = drawdown_frame.iloc[visible_positions]
        visible_auc_df = calculate_area_under_curve(visible_drawdown)
        visible_auc = dict(zip(visible_auc_df["Ticker"], visible_auc_df["AUC"]))
        visible_dates = normalized_frame.index[visible_positions]
        visible_days = (visible_dates[-1] - visible_dates[0]).days if len(visible_dates) > 1 else 0
        visible_cagr = {}
        if visible_days >= 365:
            cagr_records = calculate_cagr(normalized_frame.iloc[visible_positions]).to_dict("records")
            visible_cagr = {record["Ticker"]: record["CAGR"] for record in cagr_records}

        for ticker_name in tickers:
            auc_value = visible_auc.get(ticker_name, 0.0)
            label = f"{ticker_name} - AUC: {auc_value:.2f}"
            cagr_value = visible_cagr.get(ticker_name)
            if cagr_value is not None and np.isfinite(cagr_value):
                label += f" - CAGR: {cagr_value:.2%}"
            price_lines[ticker_name].set_label(label)
            drawdown_lines[ticker_name].set_label(f"{ticker_name} - AUC: {auc_value:.2f}")

        ax1.legend(loc="best")
        ax2.legend(loc="best")

    def _apply_visible_window(left=None, right=None, *, update_slider=True):
        nonlocal drawdown_fills

        if update_state["updating"]:
            return

        update_state["updating"] = True
        try:
            if left is None or right is None:
                left, right = ax1.get_xlim()
            left, right = _clamp_visible_window(left, right)
            visible_mask = _visible_mask_from_xlim(x_values, left, right)
            normalized_frame, drawdown_frame = _normalize_frame_to_visible_window(df_all, visible_mask)
            visible_positions = np.flatnonzero(visible_mask)

            visible_index = normalized_frame.index[visible_positions]
            for ticker_name in tickers:
                price_lines[ticker_name].set_data(visible_index, normalized_frame[ticker_name].iloc[visible_positions])
                drawdown_lines[ticker_name].set_data(visible_index, drawdown_frame[ticker_name].iloc[visible_positions])

            for fill in drawdown_fills:
                fill.remove()
            drawdown_fills = [
                ax2.fill_between(
                    visible_index,
                    drawdown_frame[ticker_name].iloc[visible_positions],
                    alpha=0.5,
                    color=ticker_colors[ticker_name],
                )
                for ticker_name in tickers
            ]

            _set_padded_ylim(ax1, normalized_frame.iloc[visible_positions].to_numpy())
            _set_padded_ylim(ax2, drawdown_frame.iloc[visible_positions].to_numpy(), zero_top=True)
            _update_price_annotations(normalized_frame, visible_mask)
            _update_visible_legends(normalized_frame, drawdown_frame, visible_positions)
            window_label = f"from {_format_num_date(left)} to {_format_num_date(right)} in {interval} intervals"
            view_range_text.set_text(window_label)
            for axis in (ax1, ax2):
                axis.set_xlim(left, right, emit=False)

            if update_slider:
                update_state["syncing_slider"] = True
                try:
                    view_slider.set_val((left, right))
                finally:
                    update_state["syncing_slider"] = False
        finally:
            update_state["updating"] = False

    def _on_xlim_changed(_ax):
        if update_state["skip_xlim_callback"] or update_state["updating"]:
            return
        _apply_visible_window(update_slider=True)
        fig.canvas.draw_idle()

    def _on_slider_changed(value):
        if update_state["syncing_slider"]:
            return

        left, right = value
        update_state["skip_xlim_callback"] = True
        for axis in (ax1, ax2):
            axis.set_xlim(left, right)
        update_state["skip_xlim_callback"] = False
        _apply_visible_window(left, right, update_slider=False)
        fig.canvas.draw_idle()

    def _on_range_button(label):
        _current_left, current_right = view_slider.val
        right = min(max(current_right, data_min), data_max)
        left = max(_left_for_duration(right, label), data_min)
        left, right = _clamp_visible_window(left, right)

        update_state["skip_xlim_callback"] = True
        try:
            for axis in (ax1, ax2):
                axis.set_xlim(left, right)
        finally:
            update_state["skip_xlim_callback"] = False
        _apply_visible_window(left, right, update_slider=True)
        fig.canvas.draw_idle()

    button_labels = ["7d", "30d", "3m", "6m", "1y", "2y", "3y"]
    button_width = 0.07
    button_gap = 0.012
    buttons_total_width = len(button_labels) * button_width + (len(button_labels) - 1) * button_gap
    button_left = 0.5 - buttons_total_width / 2
    for button_index, label in enumerate(button_labels):
        button_ax = fig.add_axes([button_left + button_index * (button_width + button_gap), 0.025, button_width, 0.035])
        button = Button(button_ax, label)
        button.on_clicked(lambda _event, button_label=label: _on_range_button(button_label))
        range_buttons.append(button)

    fig._fplot_widgets = [view_slider, *range_buttons]

    ax1.callbacks.connect("xlim_changed", _on_xlim_changed)
    view_slider.on_changed(_on_slider_changed)
    ax1.set_xlim(initial_left, initial_right)
    _apply_visible_window(initial_left, initial_right, update_slider=False)

    # Add interactive cursor functionality
    cursor1 = mplcursors.cursor(ax1)
    cursor1.connect(
        "add",
        lambda sel: (
            sel.annotation.set_text(f"{sel.artist.get_label().split(' - ')[0]}: {sel.target[1]:.2f}"),
            sel.annotation.get_bbox_patch().set(fc=sel.artist.get_color()),
        ),
    )

    cursor2 = mplcursors.cursor(ax2)
    cursor2.connect(
        "add",
        lambda sel: (
            sel.annotation.set_text(f"{sel.artist.get_label().split(' - ')[0]}: {sel.target[1]:.2f}"),
            sel.annotation.get_bbox_patch().set(fc=sel.artist.get_color()),
        ),
    )

    # Add mouse-wheel zoom for line chart (uses matplotlib date x-axis)
    def _on_scroll_line(event):
        if event.inaxes is None:
            return
        cur_xlim = ax1.get_xlim()
        xdata = event.xdata
        if xdata is None:
            xdata = (cur_xlim[0] + cur_xlim[1]) / 2
        scale = 0.8 if event.button == "up" else 1.25
        new_width = (cur_xlim[1] - cur_xlim[0]) * scale
        rel = (xdata - cur_xlim[0]) / (cur_xlim[1] - cur_xlim[0])
        new_left = xdata - new_width * rel
        new_right = xdata + new_width * (1 - rel)
        if new_left < data_min:
            new_right += data_min - new_left
            new_left = data_min
        if new_right > data_max:
            new_left -= new_right - data_max
            new_right = data_max
        ax1.set_xlim(new_left, new_right)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("scroll_event", _on_scroll_line)
    import matplotlib.dates as mdates

    _attach_drag_pan(
        fig,
        [ax1, ax2],
        clamp_min=mdates.date2num(df_all.index[0]),
        clamp_max=mdates.date2num(df_all.index[-1]),
    )

    # Print interactive help
    print("\n💡 Scroll to zoom, drag to pan, Home button to reset view")

    # plt.tight_layout()
    plt.show()


# %%
if __name__ == "__main__":
    display_plot()
