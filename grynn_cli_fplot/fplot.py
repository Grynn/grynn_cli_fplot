import re
import click
from datetime import datetime
from dateutil.relativedelta import relativedelta
import yfinance
import matplotlib.pyplot as plt
import mplcursors

# TODO: If time > 1 year, display CAGR

def parse_start_date(date_or_offset) -> datetime:
    if date_or_offset is None:
        return datetime.now() - relativedelta(years=1)
    elif isinstance(date_or_offset, str):
        if date_or_offset.upper() == "YTD":
            return datetime(datetime.now().year, 1, 1)
        elif re.match(r"^(?:last\s*)?(\d+)\s*(m|mos|mths|mo|months|days|d|yrs|y|weeks?|wks?|wk)\s*(?:ago)?$", date_or_offset):
            match = re.match(r"^(?:last\s*)?(\d+)\s*(m|mos|mths|mo|months|days|d|yrs|y|weeks?|wks?|wk)\s*(?:ago)?$", date_or_offset)
            num = int(match.group(1))
            unit = match.group(2)
            if unit in ["m", "mo", "mos", "mths", "months"]:
                return datetime.now() - relativedelta(months=num)
            elif unit in ["d", "days"]:
                return datetime.now() - relativedelta(days=num)
            elif unit in ["y", "yrs"]:
                return datetime.now() - relativedelta(years=num)
            elif unit in ["w", "wk", "wks", "week", "weeks"]:
                return datetime.now() - relativedelta(weeks=num)
            else:
                raise ValueError(f"Invalid unit: {unit} in expression {date_or_offset}")
        else:
            try:
                import dateparser
                parsed_date = dateparser.parse(date_or_offset)
                if parsed_date is None:
                    raise ValueError(f"Invalid date '{date_or_offset}'")
                return parsed_date
            except Exception as e:
                raise ValueError(f"Invalid date '{date_or_offset}'")
    elif isinstance(date_or_offset, datetime):
        return date_or_offset
    else:
        raise ValueError(f"Invalid date '{date_or_offset}'")

def gather_data(ticker, since, interval="1d"):
    """Download data from Yahoo Finance"""
    if isinstance(ticker, str):
        tickers = [*ticker.split(",")]
    
    tickers = set(tickers)
    if len(tickers) == 1: tickers.add("SPY")

    ## correct common mistakes
    ## acceptable intervals are 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    ## if interval = 1w, map to 1wk
    if interval == "1w": interval = "1wk"
    if re.match(r"3m$", interval): interval = "3mo"
    if interval == "day": interval = "1d"
    if interval == "week": interval = "1wk"
    if interval == "month": interval = "1mo"
    df = yfinance.download(tickers, start=since, interval=interval)["Adj Close"]

    return df


@click.command("plot")
@click.option("--since", type=str, default=None)
@click.option("--interval", type=str, default="1d")
@click.argument("ticker", type=str, nargs=1, required=True)
def display_plot(ticker, since, interval="1mo"):
    """Generate a plot of the given ticker(s)"""
    if (since is None):
        since = datetime.now() - relativedelta(years=1)
    else:
        since = parse_start_date(since)

    df = gather_data(ticker, since, interval)
    tickers = df.columns.tolist()
    
    click.echo(f"Generating plot for {','.join(tickers)} since {since.date()}. Interval: {interval}")
    
    #Normalize the price data (so we can compare them, all tickers start at $100)
    df = df.div(df.iloc[0]).mul(100)
    df_dd = df.div(df.cummax()).sub(1)    

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), sharex=True)

    # Generate color mapping, assign 'SPY' to gray
    tickers_in_df = df.columns.tolist()
    color_map = plt.get_cmap('tab10')
    color_iter = iter(color_map.colors)
    colors = []

    for t in tickers_in_df:
        if t == 'SPY':
            colors.append('darkgrey')
        else:
            colors.append(next(color_iter))

    # Plot the normalized price data with specified colors
    df.plot(ax=ax1, color=colors)
    ax1.set_title(f"{','.join(tickers)} Price")
    ax1.set_ylabel("Normalized Price")

    # Plot the drawdowns with the same colors
    df_dd.plot(ax=ax2, color=colors)
    ax2.set_title(f"{','.join(tickers)} Drawdowns")
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel(f"from {since.date()} to {datetime.now().date()} in {interval} intervals")

    # Add annotations with text color matching line color
    for line in ax1.get_lines():
        y = line.get_ydata()[-1]
        x = line.get_xdata()[-1]
        label = line.get_label()
        ax1.annotate(f"{label}: {y-100:.2f}%", xy=(x, y), color=line.get_color())

    # Add interactive features
    mplcursors.cursor(ax1).connect("add", lambda sel: (
        sel.annotation.set_text(f"{sel.artist.get_label()}: {sel.target[1]:.2f}"),
        sel.annotation.set_color(sel.artist.get_color())
    ))
    mplcursors.cursor(ax2).connect("add", lambda sel: (
        sel.annotation.set_text(f"{sel.artist.get_label()}: {sel.target[1]:.2f}"),
        sel.annotation.set_color(sel.artist.get_color())
    ))
    
    plt.tight_layout()
    plt.show()
    return

