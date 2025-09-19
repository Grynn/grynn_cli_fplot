import importlib.metadata
import sys
import tempfile
from datetime import datetime

import click
import matplotlib.pyplot as plt
import mplcursors
import numpy as np
from grynn_pylib.finance.timeseries import rolling_cagr
from loguru import logger
from tabulate import tabulate

from grynn_fplot.core import (
    calculate_area_under_curve,
    calculate_cagr,
    calculate_drawdowns,
    download_ticker_data,
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
@click.argument("ticker", type=str, nargs=1, required=False)
@click.option("--version", "-v", is_flag=True, help="Show version and exit")
@click.option("--debug", is_flag=True, help="Enable debug mode")
@click.option("--call", is_flag=True, help="List all available call options for the ticker")
@click.option("--put", is_flag=True, help="List all available put options for the ticker")
@click.option("--max", "max_expiry", type=str, default="6m", help="Maximum expiry time for options (e.g., '3m', '6m', '1y'). Default: 6m")
@click.option("--all", "show_all", is_flag=True, help="Show all available expiries (overrides --max)")
@click.option("--web", "-w", is_flag=True, help="Launch interactive web interface")
@click.option("--port", type=int, default=8000, help="Port for web interface")
@click.option("--host", type=str, default="127.0.0.1", help="Host for web interface")
@click.option("--no-browser", is_flag=True, help="Don't automatically open browser")
def display_plot(ticker, since, interval, version, debug, call, put, max_expiry, show_all, web, port, host, no_browser):
    """Generate a plot of the given ticker(s) or list options contracts.
    
    When --call or --put flags are used, lists available options contracts
    in a format suitable for filtering with tools like fzf.
    
    Output format: TICKER STRIKE[C|P] DAYS_TO_EXPIRY (price, return_metric)
    - For calls: return_metric is CAGR to breakeven
    - For puts: return_metric is annualized return
    
    Examples:
    \b
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

    # Launch web interface if --web flag is used
    if web:
        launch_web_interface(ticker, since, interval, port, host, no_browser, debug)
        return

    # CLI mode - require ticker
    if not ticker:
        click.echo(
            "Error: Missing argument 'TICKER'. Please provide a ticker symbol or symbols as a comma separated list."
        )
        click.echo("Hint: Use --web or -w to launch the interactive web interface.")
        return

    # Handle options listing
    if call:
        options_list = format_options_for_display(ticker, 'calls', max_expiry=max_expiry, show_all=show_all)
        if not options_list:
            click.echo(f"No call options found for {ticker.upper()}")
            return
        
        for option in options_list:
            print(option)
        return
    
    if put:
        options_list = format_options_for_display(ticker, 'puts', max_expiry=max_expiry, show_all=show_all)
        if not options_list:
            click.echo(f"No put options found for {ticker.upper()}")
            return
        
        for option in options_list:
            print(option)
        return

    # Continue with original CLI plotting logic
    display_cli_plot(ticker, since, interval, debug)


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
                    subprocess.run(["npx", "open-in-browser", url], 
                                 check=False, capture_output=True, timeout=10)
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
            workers=1,     # Single worker for CLI mode
            loop="asyncio"  # Use asyncio for better performance
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


def display_cli_plot(ticker, since, interval, debug):
    """Display plot using matplotlib (original CLI functionality)"""
    since = parse_start_date(since)

    # Download and prepare data
    df = download_ticker_data(ticker, since, interval)
    if df.empty:
        print(f"No data found for the given tickers({ticker}).")
        return

    tickers = df.columns.tolist()
    print(f"Generating plot for {', '.join(tickers)} since {since.date()}. Interval: {interval}")

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

    # Prepare for plotting
    auc_values = dict(zip(df_auc["Ticker"], df_auc["AUC"]))
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(16, 12), sharex=True, gridspec_kw={"height_ratios": [3, 2], "hspace": 0.3}
    )

    # Generate colors for each ticker
    color_map = plt.get_cmap("tab10")
    color_iter = iter(color_map.colors)
    colors = [next(color_iter) if t != "SPY" else "darkgrey" for t in tickers]

    # Plot normalized prices
    for i, ticker in enumerate(tickers):
        label = f"{ticker} - AUC: {auc_values[ticker]:.2f}"
        # Add CAGR to label if applicable
        if (df_days >= 365) and ticker in cagr_df["Ticker"].values:
            cagr_value = cagr_df.loc[cagr_df["Ticker"] == ticker, "CAGR"].values[0]
            label += f" - CAGR: {cagr_value:.2%}"

        ax1.plot(df_normalized.index, df_normalized[ticker], label=label, color=colors[i])

    ax1.set_title(f"{', '.join(tickers)} Price")
    ax1.set_ylabel("Normalized Price")
    ax1.legend(loc="best")

    # Plot drawdowns
    for i, ticker in enumerate(tickers):
        ax2.plot(df_dd.index, df_dd[ticker], label=f"{ticker} - AUC: {auc_values[ticker]:.2f}", color=colors[i])
        ax2.fill_between(df_dd.index, df_dd[ticker], alpha=0.5, color=colors[i])

    ax2.set_title(f"{', '.join(tickers)} Drawdowns")
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel(f"from {since.date()} to {datetime.now().date()} in {interval} intervals")
    ax2.legend(loc="best")

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

    # plt.tight_layout()
    plt.show()


# %%
if __name__ == "__main__":
    display_plot()
