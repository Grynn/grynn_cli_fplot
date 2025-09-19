import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Union

try:
    import yfinance
except ImportError:
    yfinance = None
import pandas as pd
from sklearn.metrics import auc
import numpy as np
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
        # Handle web interface short formats: 1m, 3m, 6m, 1y, 2y, 5y
        elif re.match(r"^(\d+)(m|y)$", date_or_offset, re.IGNORECASE):
            match = re.match(r"^(\d+)(m|y)$", date_or_offset, re.IGNORECASE)
            num = int(match.group(1))
            unit = match.group(2).lower()
            if unit == "m":
                return datetime.now() - relativedelta(months=num)
            elif unit == "y":
                return datetime.now() - relativedelta(years=num)
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


def normalize_prices(df: Union[pd.Series, pd.DataFrame], start=100):
    """Normalize prices to a starting value of 100"""
    return df.div(df.iloc[0]).mul(start)


def calculate_drawdowns(df: Union[pd.Series, pd.DataFrame]) -> Union[pd.Series, pd.DataFrame]:
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
        with open(cache_file, "r") as f:
            cached_data = json.load(f)

        # Check if cache is less than 1 hour old
        cache_time = datetime.fromisoformat(cached_data["timestamp"])
        if (datetime.now() - cache_time).total_seconds() < 3600:
            return cached_data["data"]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return None


def cache_options_data(ticker: str, data: dict):
    """Cache options data for a ticker"""
    cache_file = get_cache_dir() / f"{ticker.upper()}_options.json"

    cached_data = {"timestamp": datetime.now().isoformat(), "data": data}

    try:
        with open(cache_file, "w") as f:
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

        options_data = {"expiry_dates": expiry_dates, "calls": {}, "puts": {}}

        # Fetch call and put options for each expiry date
        for expiry in expiry_dates:
            try:
                option_chain = stock.option_chain(expiry)
                options_data["calls"][expiry] = option_chain.calls.to_dict("records")
                options_data["puts"][expiry] = option_chain.puts.to_dict("records")
            except Exception:
                continue  # Skip this expiry if there's an error

        # Cache the data
        cache_options_data(ticker, options_data)
        return options_data

    except Exception:
        return None


def parse_time_expression(time_expr: str) -> int:
    """Parse time expression like '3m', '6m', '1y' and return days

    Args:
        time_expr: Time expression (e.g., '3m', '6m', '1y', '2w', '30d')

    Returns:
        Number of days
    """
    if not time_expr:
        return 180  # Default 6 months

    time_expr = time_expr.lower().strip()

    # Extract number and unit
    match = re.match(r"^(\d+)([mdwy])$", time_expr)
    if not match:
        return 180  # Default 6 months if parsing fails

    num = int(match.group(1))
    unit = match.group(2)

    if unit == "d":
        return num
    elif unit == "w":
        return num * 7
    elif unit == "m":
        return num * 30  # Approximate month as 30 days
    elif unit == "y":
        return num * 365
    else:
        return 180  # Default 6 months


def get_spot_price(ticker: str) -> float:
    """Get current spot price for a ticker"""
    if yfinance is None:
        return 100.0  # Fallback value for testing

    try:
        stock = yfinance.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 100.0  # Fallback value


def calculate_cagr_to_breakeven(spot_price: float, strike: float, option_price: float, dte: int) -> float:
    """Calculate CAGR to breakeven for call options

    This is a simplified implementation. In the real implementation,
    this should use grynn_pylib's options module.
    """
    if dte <= 0 or option_price <= 0:
        return 0.0

    # Breakeven price for calls = strike + premium
    breakeven_price = strike + option_price

    # Calculate required return to reach breakeven
    if spot_price <= 0:
        return 0.0

    total_return = (breakeven_price / spot_price) - 1

    # Annualize the return
    years = dte / 365.0
    if years <= 0:
        return 0.0

    cagr = (1 + total_return) ** (1 / years) - 1
    return cagr


def calculate_put_annualized_return(spot_price: float, option_price: float, dte: int) -> float:
    """Calculate annualized return for put options

    Formula: (price / (spot - price)) * 365 / dte
    """
    if dte <= 0 or option_price <= 0:
        return 0.0

    denominator = spot_price - option_price
    if denominator <= 0:
        return 0.0

    return (option_price / denominator) * 365 / dte


def filter_expiry_dates(expiry_dates: list, max_days: int, show_all: bool = False) -> list:
    """Filter expiry dates based on maximum days from now

    Args:
        expiry_dates: List of expiry date strings
        max_days: Maximum number of days from now
        show_all: If True, return all dates (ignore max_days)
    """
    if show_all:
        return expiry_dates

    current_date = datetime.now()
    filtered_dates = []

    for expiry_str in expiry_dates:
        try:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
            days_to_expiry = (expiry_date - current_date).days

            if days_to_expiry <= max_days and days_to_expiry >= 0:
                filtered_dates.append(expiry_str)
        except ValueError:
            continue  # Skip invalid date formats

    return filtered_dates


def calculate_days_to_expiry(expiry_date_str: str) -> int:
    """Calculate days to expiry from expiry date string"""
    try:
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d")
        return (expiry_date - datetime.now()).days
    except ValueError:
        return 0


def format_options_for_display(
    ticker: str, option_type: str = "calls", sort_by: str = "strike", max_expiry: str = "6m", show_all: bool = False
):
    """Format options data for fzf-friendly display with enhanced information

    Args:
        ticker: Stock ticker symbol
        option_type: 'calls' or 'puts'
        sort_by: 'strike', 'dte', or 'volume' (default: 'strike')
        max_expiry: Maximum expiry time (e.g., '3m', '6m', '1y'). Default: '6m'
        show_all: Show all available expiries (overrides max_expiry)
    """
    options_data = fetch_options_data(ticker)

    if not options_data:
        return []

    # Get spot price for return calculations
    spot_price = get_spot_price(ticker)

    # Filter expiry dates based on max_expiry
    max_days = parse_time_expression(max_expiry)
    filtered_expiry_dates = filter_expiry_dates(options_data.get("expiry_dates", []), max_days, show_all)

    formatted_options = []

    for expiry_date in filtered_expiry_dates:
        if expiry_date not in options_data.get(option_type, {}):
            continue

        options_list = options_data[option_type][expiry_date]
        dte = calculate_days_to_expiry(expiry_date)

        for option in options_list:
            strike = option.get("strike", 0)
            volume = option.get("volume", 0) or 0  # Handle None values
            last_price = option.get("lastPrice", 0) or 0

            # Calculate return metric based on option type
            if option_type == "calls" and last_price > 0:
                return_metric = calculate_cagr_to_breakeven(spot_price, strike, last_price, dte)
                return_str = f"{return_metric:.2%}"
            elif option_type == "puts" and last_price > 0:
                return_metric = calculate_put_annualized_return(spot_price, last_price, dte)
                return_str = f"{return_metric:.2%}"
            else:
                return_str = "N/A"

            # Format as "TICKER STRIKEC/P XDTE (price, return)"
            option_type_letter = "C" if option_type == "calls" else "P"
            formatted_option = (
                f"{ticker.upper()} {strike:.0f}{option_type_letter} {dte}DTE (${last_price:.2f}, {return_str})"
            )

            # Store additional data for sorting
            formatted_options.append(
                {"display": formatted_option, "strike": strike, "dte": dte, "volume": volume, "price": last_price}
            )

    # Sort based on the specified criteria
    if sort_by == "strike":
        formatted_options.sort(key=lambda x: x["strike"])
    elif sort_by == "dte":
        formatted_options.sort(key=lambda x: x["dte"])
    elif sort_by == "volume":
        formatted_options.sort(key=lambda x: x["volume"], reverse=True)

    # Return just the display strings
    return [option["display"] for option in formatted_options]
