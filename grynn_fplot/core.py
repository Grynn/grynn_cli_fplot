import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
try:
    import yfinance
except ImportError:
    yfinance = None
import pandas as pd
from sklearn.metrics import auc
import numpy as np
import os
import json
from pathlib import Path


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


def parse_interval(interval="1d"):
    # Correct common mistakes
    interval_corrections = {
        "1w": "1wk",
        "3m": "3mo",
        "day": "1d",
        "week": "1wk",
        "month": "1mo",
    }
    interval = interval_corrections.get(interval, interval)
    return interval


def download_ticker_data(ticker, since, interval="1d"):
    """Download data from Yahoo Finance"""
    if yfinance is None:
        raise ImportError("yfinance package is required for ticker data functionality")
        
    if isinstance(ticker, str):
        tickers = [t.strip() for t in ticker.split(",")]
    else:
        tickers = ticker

    tickers = set(tickers)
    if len(tickers) == 1:
        tickers.add("SPY")

    interval = parse_interval(interval)

    # Only pass start parameter if since is not None
    kwargs = {"interval": interval, "auto_adjust": False}
    if since is not None:
        kwargs["start"] = since

    df = yfinance.download(tickers, **kwargs)["Adj Close"]
    assert isinstance(df, pd.DataFrame), f"Expected DataFrame from yfinance.download for {tickers}"

    return df


def normalize_prices(df: pd.Series | pd.DataFrame, start=100):
    """Normalize prices to a starting value of 100"""
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
    return pd.DataFrame(auc_values.items(), columns=["Ticker", "AUC"]).sort_values(by="AUC", ascending=False)


def calculate_cagr(df):
    """Calculate Compound Annual Growth Rate for DataFrame
    Each column is treated as a separate ticker, values are prices.

    CAGR = (End Value / Start Value)^(1 / Years) - 1
    """
    # Calculate total timeframe covered by the dataframe; we only care about the first and last values
    start_date = df.index[0]
    end_date = df.index[-1]
    assert start_date < end_date, "Dataframe must be sorted by date"
    days = (end_date - start_date).days
    years = days / 365.25

    if days < 365:
        return None  # CAGR only makes sense for periods > 1 year

    cagr = {}
    for column in df.columns:
        start_value = df[column].iloc[0]
        end_value = df[column].iloc[-1]
        if start_value > 0:  # Avoid division by zero
            cagr[column] = (end_value / start_value) ** (1 / years) - 1
        else:
            cagr[column] = None

    return pd.DataFrame(list(cagr.items()), columns=["Ticker", "CAGR"]).sort_values(by="CAGR", ascending=False)


def get_years(df):
    start_date = df.index[0]
    end_date = df.index[-1]
    return (end_date - start_date).days / 365.25


def get_cache_dir():
    """Get the cache directory for options data"""
    cache_dir = Path.home() / ".cache" / "grynn_fplot"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_cached_options_data(ticker: str):
    """Get cached options data for a ticker if it exists and is recent"""
    cache_file = get_cache_dir() / f"{ticker.upper()}_options.json"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, 'r') as f:
            cached_data = json.load(f)
        
        # Check if cache is less than 1 hour old
        cache_time = datetime.fromisoformat(cached_data['timestamp'])
        if (datetime.now() - cache_time).total_seconds() < 3600:
            return cached_data['data']
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    
    return None


def cache_options_data(ticker: str, data: dict):
    """Cache options data for a ticker"""
    cache_file = get_cache_dir() / f"{ticker.upper()}_options.json"
    
    cached_data = {
        'timestamp': datetime.now().isoformat(),
        'data': data
    }
    
    try:
        with open(cache_file, 'w') as f:
            json.dump(cached_data, f)
    except Exception:
        pass  # Silently fail if caching doesn't work


def fetch_options_data(ticker: str):
    """Fetch options data for a ticker from yfinance with caching"""
    if yfinance is None:
        raise ImportError("yfinance package is required for options functionality")
        
    # Try to get cached data first
    cached_data = get_cached_options_data(ticker)
    if cached_data:
        return cached_data
    
    try:
        stock = yfinance.Ticker(ticker)
        expiry_dates = stock.options
        
        if not expiry_dates:
            return None
        
        options_data = {
            'expiry_dates': expiry_dates,
            'calls': {},
            'puts': {}
        }
        
        # Fetch call and put options for each expiry date
        for expiry in expiry_dates:
            try:
                option_chain = stock.option_chain(expiry)
                options_data['calls'][expiry] = option_chain.calls.to_dict('records')
                options_data['puts'][expiry] = option_chain.puts.to_dict('records')
            except Exception:
                continue  # Skip this expiry if there's an error
        
        # Cache the data
        cache_options_data(ticker, options_data)
        return options_data
        
    except Exception:
        return None


def calculate_days_to_expiry(expiry_date_str: str) -> int:
    """Calculate days to expiry from expiry date string"""
    try:
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d')
        return (expiry_date - datetime.now()).days
    except ValueError:
        return 0


def format_options_for_display(ticker: str, option_type: str = 'calls'):
    """Format options data for fzf-friendly display"""
    options_data = fetch_options_data(ticker)
    
    if not options_data:
        return []
    
    formatted_options = []
    
    for expiry_date, options_list in options_data.get(option_type, {}).items():
        dte = calculate_days_to_expiry(expiry_date)
        
        for option in options_list:
            strike = option.get('strike', 0)
            # Format as "TICKER STRIKEC/P XDTE"
            option_type_letter = 'C' if option_type == 'calls' else 'P'
            formatted_option = f"{ticker.upper()} {strike:.0f}{option_type_letter} {dte}DTE"
            formatted_options.append(formatted_option)
    
    # Sort by strike price (extract from the formatted string)
    formatted_options.sort(key=lambda x: float(x.split()[1].rstrip('CP')))
    
    return formatted_options
