import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
import yfinance
import pandas as pd
from sklearn.metrics import auc
import numpy as np


def parse_start_date(date_or_offset) -> datetime | None:
    if date_or_offset is None:
        return datetime.now() - relativedelta(years=1)
    elif isinstance(date_or_offset, str):
        if date_or_offset.lower() == "max":
            return None
        elif date_or_offset.upper() == "YTD":
            return datetime(datetime.now().year, 1, 1)
        elif re.match(
            r"^(?:last\s*)?(\d+)\s*(m|mos|mths|mo|months|days|d|yrs|yr|y|weeks?|wks?|wk)\s*(?:ago)?$",
            date_or_offset,
            re.IGNORECASE,
        ):
            match = re.match(
                r"^(?:last\s*)?(\d+)\s*(m|mos|mths|mo|months|days|d|yrs|yr|y|weeks?|wks?|wk)\s*(?:ago)?$",
                date_or_offset,
                re.IGNORECASE,
            )
            num = int(match.group(1))
            unit = match.group(2).lower()
            if unit in ["m", "mo", "mos", "mths", "months"]:
                return datetime.now() - relativedelta(months=num)
            elif unit in ["d", "days"]:
                return datetime.now() - relativedelta(days=num)
            elif unit in ["y", "yr", "yrs"]:
                return datetime.now() - relativedelta(years=num)
            elif unit in ["w", "wk", "wks", "week", "weeks"]:
                return datetime.now() - relativedelta(weeks=num)
            else:
                raise ValueError(f"Invalid unit: {unit} in expression '{date_or_offset}'")
        else:
            try:
                from dateparser import parse

                parsed_date = parse(date_or_offset)
                if parsed_date is None:
                    raise ValueError(f"Invalid date '{date_or_offset}'")
                return parsed_date
            except Exception:
                raise ValueError(f"Invalid date '{date_or_offset}'")
    elif isinstance(date_or_offset, datetime):
        return date_or_offset
    else:
        raise ValueError(f"Invalid date '{date_or_offset}'")


def download_ticker_data(ticker, since, interval="1d"):
    """Download data from Yahoo Finance"""
    if isinstance(ticker, str):
        tickers = [t.strip() for t in ticker.split(",")]
    else:
        tickers = ticker

    tickers = set(tickers)
    if len(tickers) == 1:
        tickers.add("SPY")

    # Correct common mistakes
    interval_corrections = {
        "1w": "1wk",
        "3m": "3mo",
        "day": "1d",
        "week": "1wk",
        "month": "1mo",
    }
    interval = interval_corrections.get(interval, interval)

    # Only pass start parameter if since is not None
    kwargs = {"interval": interval, "auto_adjust": False}
    if since is not None:
        kwargs["start"] = since

    df = yfinance.download(tickers, **kwargs)["Adj Close"]
    if isinstance(df, pd.Series):
        df = df.to_frame()
    return df


def normalize_prices(df: pd.Series | pd.DataFrame, start=100):
    return df.div(df.iloc[0]).mul(start)


def calculate_drawdowns(df: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    return df.div(df.cummax()).sub(1)


def calculate_area_under_curve(df_dd):
    """Calculate area under curve for drawdown dataframe using sklearn.auc"""
    auc_values = {}
    for column in df_dd.columns:
        # Get x and y values, dropping NaN values
        data = df_dd[[column]].dropna()
        if len(data) > 1:
            # x values are the index positions (time points)
            x = np.arange(len(data))
            # y values are the absolute drawdown values
            y = abs(data[column].values)
            # Calculate AUC using sklearn's auc function
            auc_values[column] = auc(x, y)
        else:
            auc_values[column] = 0.0
    return pd.DataFrame(auc_values.items(), columns=['Ticker', 'AUC']).sort_values(by='AUC', ascending=False)


def calculate_cagr(df):
    """Calculate Compound Annual Growth Rate for price data
    
    CAGR = (End Value / Start Value)^(1 / Years) - 1
    """
    # Calculate total years
    start_date = df.index[0]
    end_date = df.index[-1]
    years = (end_date - start_date).days / 365.25
    
    if years <= 1:
        return None  # CAGR only makes sense for periods > 1 year
    
    cagr = {}
    for column in df.columns:
        start_value = df[column].iloc[0]
        end_value = df[column].iloc[-1]
        if start_value > 0:  # Avoid division by zero
            cagr[column] = (end_value / start_value) ** (1 / years) - 1
        else:
            cagr[column] = None
            
    return pd.DataFrame(list(cagr.items()), columns=['Ticker', 'CAGR']).sort_values(by='CAGR', ascending=False)


def is_long_term(df):
    """Check if the time frame is more than 1 year (365 days)"""
    start_date = df.index[0]
    end_date = df.index[-1]
    return (end_date - start_date).days > 365
