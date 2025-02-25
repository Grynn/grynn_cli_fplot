# %%
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation


def plot_drawdowns(data):
    """
    Plot the drawdowns for stock data (timeseries)

    Parameters:
    data (pd.DataFrame|pd.Series|array): The stock data.
    """
    plt.figure(figsize=(12, 6))

    columns = data.columns if isinstance(data, pd.DataFrame) else [data.name]

    for ticker in columns:
        cmax = data[ticker].cummax()
        drawdowns = (data[ticker] - cmax) / cmax
        plt.plot(data.index, drawdowns, lw=1, label=ticker)
        plt.fill_between(data.index, drawdowns, alpha=0.5)

    plt.title(f"Drawdown Chart for {', '.join(tickers)}")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.grid(True)
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.legend()
    plt.show()


def plot_returns(data):
    """
    Plot the drawdowns for stock data (timeseries)

    Parameters:
    data (pd.DataFrame|pd.Series|array): The stock data.
    """
    fig = plt.figure(figsize=(12, 6))
    ax = plt.gca()

    columns = data.columns if isinstance(data, pd.DataFrame) else [data.name]

    lines = []
    for ticker in columns:
        initial_value = data[ticker].iloc[0]
        drawdowns = (data[ticker] - initial_value) / initial_value
        (line,) = plt.plot([], [], lw=1, label=ticker)
        plt.fill_between(data.index, drawdowns, alpha=0.5)
        lines.append(line)

    plt.title(f"Drawdown Chart for {', '.join(tickers)}")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.grid(True)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    plt.legend()
    plt.show()

    def animate(i):
        for line, ticker in zip(lines, columns):
            initial_value = data[ticker].iloc[i:]
            drawdowns = (data[ticker] - initial_value) / initial_value
            line.set_data(data.index[i:], drawdowns[i:])
        return lines

    animation.FuncAnimation(fig, animate, frames=len(data), interval=200, blit=True)
    # display(ani.to_html5_video())


tickers = ["TSLA", "QQQ", "AAPL"]
period = "5y"
data = yf.download(tickers, period=period)["Adj Close"]
plot_returns(data)
plot_drawdowns(data)

# plot what: drawdowns,price,rolling_3y_cagr,beta,alpha
# tickers
