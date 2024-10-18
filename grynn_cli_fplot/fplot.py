import re
import click
import datetime
from dateutil import parser, relativedelta
import yfinance
import matplotlib.pyplot as plt

# TODO: If time > 1 year, display CAGR


@click.command("plot")
@click.option("--since", type=str, default=None)
@click.option("--interval", type=str, default="1d")
@click.argument("ticker", type=str, nargs=1, required=True)
def generate_plot(ticker, since, interval="1mo"):
    """Generate a plot of the given ticker(s)"""
    if (since is None):
        since = datetime.datetime.now() - relativedelta.relativedelta(years=1)
    elif (isinstance(since, str)):
        if (since.upper() == "YTD"):
            since = datetime.datetime(datetime.datetime.now().year, 1, 1)
        elif re.match(r"(last)? \d+ ?(m|mos|days|d|yrs|y)$", since):
            num = int(re.match(r"\d+", since).group())
            unit = re.search(r"(m|mos|days|d|yrs|y)$", since).group()
            if unit in ["m", "mos"]:
                since = datetime.datetime.now() - relativedelta.relativedelta(months=num)
            elif unit in ["d", "days"]:
                since = datetime.datetime.now() - relativedelta.relativedelta(days=num)
            elif unit in ["y", "yrs"]:
                since = datetime.datetime.now() - relativedelta.relativedelta(years=num)
            else:
                click.echo(f"Invalid unit: {unit}", err=True)
        else:
            try:
                import dateparser
                since = dateparser.parse(since)
            except Exception as e:
                click.echo("Invalid since date")
                click.error(e)
                return
    elif not isinstance(since, datetime.datetime):
        # since is not a string, nor a datetime object
        click.echo("Invalid since date")
        return
                
    if not isinstance(since, datetime.datetime):
        since = parser.parse(since)

    if isinstance(ticker, str):
        tickers = [*ticker.split(",")]
    
    tickers = list(set(tickers))
    if len(tickers) == 1: tickers.append("SPY")

    ## correct common mistakes
    ## acceptable intervals are 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    ## if interval = 1w, map to 1wk
    if interval == "1w": interval = "1wk"
    if re.match(r"3m$", interval): interval = "3mo"
    if interval == "day": interval = "1d"
    if interval == "week": interval = "1wk"
    if interval == "month": interval = "1mo"

    click.echo(f"Generating plot for {','.join(tickers)} since {since.date()}. Interval: {interval}")

    df = yfinance.download(tickers, start=since, interval=interval)["Adj Close"]
    
    #Normalize the price data (so we can compare them, all tickers start at $100)
    df = df.div(df.iloc[0]).mul(100)
    df_dd = df.div(df.cummax()).sub(1)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), sharex=True)

    # Plot the normalized price data
    df.plot(ax=ax1)
    ax1.set_title(f"{','.join(tickers)} Price")
    ax1.set_ylabel("Normalized Price")

    # Plot the drawdowns
    df_dd.plot(ax=ax2)
    ax2.set_title(f"{','.join(tickers)} Drawdowns")
    ax2.set_ylabel("Drawdown")
    ax2.set_xlabel(f"from {since.date()} to {datetime.datetime.now().date()} in {interval} intervals")

    # Add annotations to the end of each series in the price plot
    for col in df.columns:
        ax1.annotate(f"{col}: {df[col].iloc[-1]-100:.2f}%", (df.index[-1], df[col].iloc[-1]))

    plt.tight_layout()
    plt.show()
    return
    
