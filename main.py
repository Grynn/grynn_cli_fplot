import re
import click
import datetime
import dateutil.parser 
import dateparser
from IPython.display import display
import yfinance
import matplotlib.pyplot as plt

@click.command()
@click.option("--since", type=str, default="2024-01-00")
@click.option("--interval", type=str, default="1d")
@click.argument("ticker", type=str, nargs=1, required=True)
def generate_plot(ticker, since, interval="1mo"):
    """Generate a plot of the given ticker(s)"""
    if (isinstance(since, str)):
        if (since == "2024-01-00"):
            since = datetime.datetime.now() - datetime.timedelta(days=180)
        elif (since.upper() == "YTD"):
            since = datetime.datetime(datetime.datetime.now().year, 1, 1)
        elif re.match(r"\d+ ?(m|mos|days|d|yrs|y)$", since):
            num = int(re.match(r"\d+", since).group())
            unit = re.search(r"(m|mos|days|d|yrs|y)$", since).group()
            if unit in ["m", "mos"]:
                since = datetime.datetime.now() - datetime.timedelta(days=30*num)
            elif unit in ["d", "days"]:
                since = datetime.datetime.now() - datetime.timedelta(days=num)
            elif unit in ["y", "yrs"]:
                since = datetime.datetime.now() - datetime.timedelta(days=365*num)
            else:
                click.echo(f"Invalid unit: {unit}", err=True)
        else:
            try:
                since = dateparser.parse(since)
                # TODO try parsing with ollama
            except Exception as e:
                click.echo("Invalid since date")
                click.error(e)
                return
    elif not isinstance(since, datetime.datetime):
        # since is not a string, nor a datetime object
        click.echo("Invalid since date")
        return
                
    if not isinstance(since, datetime.datetime):
        since = dateutil.parser.parse(since)

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

    df = yfinance.download(tickers, start=since, interval=interval).Close
    df = df.div(df.iloc[0]).mul(100)
    df.plot(figsize=(16, 12))
    plt.title(f"{",".join(tickers)}")
    plt.xlabel(f"from {since.date()} to {datetime.datetime.now().date()} in {interval} intervals")

    # add annotations to the end of each series (with percent change)
    for col in df.columns:
        plt.annotate(f"{col}: {df[col].iloc[-1]-100:.2f}%", (df.index[-1], df[col].iloc[-1]))

    plt.show()
    return
    

# Not needed if called via setup.py which creates a wrapper
if __name__ == '__main__':
    generate_plot()