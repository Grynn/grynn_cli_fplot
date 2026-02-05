import importlib.metadata
import sys
import tempfile
from datetime import datetime

import click
import matplotlib.pyplot as plt
import mplcursors
import numpy as np
import mplfinance as mpf
from grynn_pylib.finance.timeseries import rolling_cagr
from loguru import logger
from tabulate import tabulate

from grynn_fplot.core import (
    calculate_area_under_curve,
    calculate_cagr,
    calculate_drawdowns,
    download_ticker_data,
    download_ohlcv_data,
    normalize_prices,
    parse_start_date,
    format_options_for_display,
)

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

    # Calculate SMAs on the full dataset
    sma_50 = df["Close"].rolling(window=50).mean()
    sma_200 = df["Close"].rolling(window=200).mean()

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

    print(
        f"Generating candlestick plot for {ticker} since {requested_since.date() if requested_since else 'max'}. Interval: {interval}"
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

    # Add scroll-zoom and date tick formatting
    _add_scroll_zoom(fig, axes, df.index)

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

    # Metrics are computed on the view window (df)
    df_normalized = normalize_prices(df)
    df_dd = calculate_drawdowns(df_normalized)
    df_auc = calculate_area_under_curve(df_dd)
    df_days = (df.index[-1] - df.index[0]).days

    # Normalize/drawdown the FULL dataset for plotting (so pan/zoom reveals all history)
    df_all_normalized = normalize_prices(df_all)
    df_all_dd = calculate_drawdowns(df_all_normalized)

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
    auc_values = dict(zip(df_auc["Ticker"], df_auc["AUC"]))
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(16, 12), sharex=True, gridspec_kw={"height_ratios": [3, 2], "hspace": 0.3}
    )

    # Generate colors for each ticker
    color_map = plt.get_cmap("tab10")
    color_iter = iter(color_map.colors)
    colors = [next(color_iter) if t != "SPY" else "darkgrey" for t in tickers]

    # Plot normalized prices (full history)
    for i, ticker_name in enumerate(tickers):
        label = f"{ticker_name} - AUC: {auc_values[ticker_name]:.2f}"
        # Add CAGR to label if applicable
        if (df_days >= 365) and ticker_name in cagr_df["Ticker"].values:
            cagr_value = cagr_df.loc[cagr_df["Ticker"] == ticker_name, "CAGR"].values[0]
            label += f" - CAGR: {cagr_value:.2%}"

        ax1.plot(df_all_normalized.index, df_all_normalized[ticker_name], label=label, color=colors[i])

    ax1.set_title(f"{', '.join(tickers)} Price (Pan/Zoom enabled - use toolbar)")
    ax1.set_ylabel("Normalized Price")
    ax1.legend(loc="best")

    # Plot drawdowns (full history)
    for i, ticker_name in enumerate(tickers):
        ax2.plot(
            df_all_dd.index,
            df_all_dd[ticker_name],
            label=f"{ticker_name} - AUC: {auc_values[ticker_name]:.2f}",
            color=colors[i],
        )
        ax2.fill_between(df_all_dd.index, df_all_dd[ticker_name], alpha=0.5, color=colors[i])

    ax2.set_title(f"{', '.join(tickers)} Drawdowns")
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel(
        f"from {since_parsed.date() if since_parsed else df_all.index[0].date()} to {datetime.now().date()} in {interval} intervals"
    )
    ax2.legend(loc="best")

    # Set initial view xlim
    if initial_view_start is not None:
        import matplotlib.dates as mdates

        ax1.set_xlim(mdates.date2num(initial_view_start), mdates.date2num(df_all.index[-1]))

    # Add end-point annotations
    for line in ax1.get_lines():
        y = line.get_ydata()[-1]
        x = line.get_xdata()[-1]
        label = line.get_label().split(" - ")[0]  # Extract just the ticker part

        # Handle masked values
        if isinstance(y, np.ma.core.MaskedConstant):
            value_text = "N/A"
        else:
            value_text = f"{y - 100:.2f}%"

        ax1.annotate(f"{label}: {value_text}", xy=(x, y), color=line.get_color())

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
        ax1.set_xlim(new_left, new_right)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("scroll_event", _on_scroll_line)

    # Print interactive help
    print("\n💡 Scroll to zoom, drag to pan, Home button to reset view")

    # plt.tight_layout()
    plt.show()


# %%
if __name__ == "__main__":
    display_plot()
