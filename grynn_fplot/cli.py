import click
import matplotlib.pyplot as plt
import mplcursors
import numpy as np
from datetime import datetime
import tempfile
import importlib.metadata
from grynn_fplot.core import (
    parse_start_date,
    download_ticker_data,
    normalize_prices,
    calculate_drawdowns,
)

try:
    # if __package__ is None and __name__ == "__main__" this is being run from the cli
    __version__ = importlib.metadata.version(__package__ or __name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = f"unknown (__name__: {__name__})"


@click.command()
@click.option("--since", type=str, default=None)
@click.option("--interval", type=str, default="1d")
@click.argument("ticker", type=str, nargs=1, required=True)
@click.option("--version", "-v", is_flag=True, help="Show version and exit")
@click.option("--debug", is_flag=True, help="Enable debug mode")
def display_plot(ticker, since, interval, version, debug):
    """Generate a plot of the given ticker(s)"""

    if version:
        print(f"fplot {__version__}\n")
        return

    since = parse_start_date(since)

    df = download_ticker_data(ticker, since, interval)
    if df.empty:
        print(f"No data found for the given tickers({ticker})).")
        return

    tickers = df.columns.tolist()

    if debug:
        print(f"Data for {', '.join(tickers)}:")
        print(df.head())
        temp_file = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        df.to_csv(temp_file.name)
        print(f"Data saved to temporary file: {temp_file.name}")

    print(f"Generating plot for {', '.join(tickers)} since {since.date()}. Interval: {interval}")

    # Normalize the price data
    df_normalized = normalize_prices(df)
    df_dd = calculate_drawdowns(df_normalized)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), sharex=True)

    # Generate color mapping, assign 'SPY' to gray
    color_map = plt.get_cmap("tab10")
    color_iter = iter(color_map.colors)
    colors = []

    for t in tickers:
        if t == "SPY":
            colors.append("darkgrey")
        else:
            colors.append(next(color_iter))

    # Plot the normalized price data
    df_normalized.plot(ax=ax1, color=colors)
    ax1.set_title(f"{', '.join(tickers)} Price")
    ax1.set_ylabel("Normalized Price")

    # Plot the drawdowns
    df_dd.plot(ax=ax2, color=colors)
    for i, t in enumerate(tickers):
        ax2.fill_between(df_dd.index, df_dd[t], alpha=0.5, color=colors[i])
    ax2.set_title(f"{', '.join(tickers)} Drawdowns")
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel(f"from {since.date()} to {datetime.now().date()} in {interval} intervals")

    # Add annotations
    for line in ax1.get_lines():
        y = line.get_ydata()[-1]
        x = line.get_xdata()[-1]
        label = line.get_label()

        # Handle masked values
        if isinstance(y, np.ma.core.MaskedConstant):
            value_text = "N/A"
        else:
            value_text = f"{y - 100:.2f}%"

        ax1.annotate(f"{label}: {value_text}", xy=(x, y), color=line.get_color())

    # Add interactive features
    mplcursors.cursor(ax1).connect(
        "add",
        lambda sel: (
            sel.annotation.set_text(f"{sel.artist.get_label()}: {sel.target[1]:.2f}"),
            sel.annotation.get_bbox_patch().set(fc=sel.artist.get_color()),
        ),
    )
    mplcursors.cursor(ax2).connect(
        "add",
        lambda sel: (
            sel.annotation.set_text(f"{sel.artist.get_label()}: {sel.target[1]:.2f}"),
            sel.annotation.get_bbox_patch().set(fc=sel.artist.get_color()),
        ),
    )

    plt.tight_layout()
    plt.show()


def display_auc():
    # Compute drawdowns for ticker x
    # show the drawdowns plot and area under curve
    # if there are multiple tickers, show the area under curve for all of them
    # divide UI into two parts (top is the chart, bottom is the AUC table)
    pass


# %%
if __name__ == "__main__":
    display_plot()
