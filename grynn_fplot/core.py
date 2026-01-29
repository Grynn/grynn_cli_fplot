import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Union, List

try:
    import yfinance
except ImportError:
    yfinance = None
import pandas as pd
from sklearn.metrics import auc
import numpy as np
import json
from pathlib import Path


def parse_ticker_input(ticker_input: Union[str, List[str]]) -> List[str]:
    """Parse ticker input supporting multiple formats.

    Supports:
    - Single ticker: "AAPL"
    - Comma-separated: "AAPL,TSLA" or "AAPL, TSLA"
    - Space-separated: ["AAPL", "TSLA"] (from CLI args)
    - Division operations: "AAPL/XLK"
    - Mixed: ["AAPL", "AAPL/XLK", "TW.L"]
    - Quoted strings with spaces/commas: "ABC, DEF" (preserved as single token by shell)

    Args:
        ticker_input: Either a single string or list of strings from CLI arguments

    Returns:
        List of ticker symbols or expressions (e.g., ["AAPL", "TSLA", "AAPL/XLK"])
    """
    if ticker_input is None:
        return []

    # If it's already a list (from multiple CLI arguments), process each element
    if isinstance(ticker_input, list):
        tickers = []
        for item in ticker_input:
            # Each item might still contain commas or be a complex expression
            if "," in item:
                # Split by comma and add each part
                tickers.extend([t.strip() for t in item.split(",") if t.strip()])
            else:
                # Keep as-is (might be a division expression or simple ticker)
                item = item.strip()
                if item:
                    tickers.append(item)
        return tickers

    # If it's a single string, split by commas
    if isinstance(ticker_input, str):
        ticker_input = ticker_input.strip()
        if not ticker_input:
            return []

        # Split by comma and strip whitespace
        tickers = [t.strip() for t in ticker_input.split(",") if t.strip()]
        return tickers

    return []


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


def download_ohlcv_data(ticker, since, interval="1d"):
    """Download OHLCV (Open, High, Low, Close, Volume) data from Yahoo Finance

    Args:
        ticker: Single ticker symbol (e.g., "AAPL")
        since: Start date (datetime object or None for max)
        interval: Data interval (e.g., "1d", "1wk", "1mo")

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
        Index is DatetimeIndex
    """
    if yfinance is None:
        raise ImportError("yfinance package is required for ticker data functionality")

    interval = parse_interval(interval)

    # Only pass start parameter if since is not None
    kwargs = {"interval": interval, "auto_adjust": False}
    if since is not None:
        kwargs["start"] = since

    # Download OHLCV data for the ticker
    ticker_obj = yfinance.Ticker(ticker)
    df = ticker_obj.history(**kwargs)

    # Return only the OHLCV columns we need
    # yfinance returns: Open, High, Low, Close, Volume (and sometimes Dividends, Stock Splits)
    ohlcv_columns = ["Open", "High", "Low", "Close", "Volume"]
    return df[ohlcv_columns]


def download_ticker_data(ticker, since, interval="1d"):
    """Download data from Yahoo Finance

    Supports:
    - Single ticker: "AAPL"
    - Comma-separated: "AAPL,TSLA"
    - List of tickers: ["AAPL", "TSLA"]
    - Division operations: "AAPL/XLK" or ["AAPL/XLK"]

    Division operations create a new column with the ratio of the two tickers.
    """
    if yfinance is None:
        raise ImportError("yfinance package is required for ticker data functionality")

    # Parse ticker input
    tickers = parse_ticker_input(ticker)

    # Separate division expressions from regular tickers
    division_expressions = []
    regular_tickers = []

    for t in tickers:
        if "/" in t:
            division_expressions.append(t)
            # Extract the component tickers from the division expression
            parts = t.split("/")
            for part in parts:
                part = part.strip()
                if part:
                    regular_tickers.append(part)
        else:
            regular_tickers.append(t)

    # Remove duplicates while preserving order
    regular_tickers = list(dict.fromkeys(regular_tickers))

    # Add SPY if only one regular ticker (not counting division expressions)
    if len(regular_tickers) == 1 and not division_expressions:
        regular_tickers.append("SPY")

    interval = parse_interval(interval)

    # Only pass start parameter if since is not None
    kwargs = {"interval": interval, "auto_adjust": False}
    if since is not None:
        kwargs["start"] = since

    # Download data for regular tickers
    df = yfinance.download(regular_tickers, **kwargs)["Adj Close"]
    assert isinstance(df, pd.DataFrame), f"Expected DataFrame from yfinance.download for {regular_tickers}"

    # Process division expressions
    for expr in division_expressions:
        parts = expr.split("/")
        if len(parts) == 2:
            numerator = parts[0].strip()
            denominator = parts[1].strip()

            if numerator in df.columns and denominator in df.columns:
                # Create new column with the division result
                df[expr] = df[numerator] / df[denominator]
            else:
                # If one of the tickers is missing, log a warning but continue
                print(f"Warning: Could not create division column '{expr}' - missing ticker data")

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


def calculate_put_annualized_return(strike_price: float, option_price: float, dte: int) -> float:
    """Calculate annualized return for put options

    Formula: premium / capital_at_risk * 365 / dte
    where capital_at_risk = strike - premium
    """
    if dte <= 0 or option_price <= 0:
        return 0.0

    capital_at_risk = strike_price - option_price
    if capital_at_risk <= 0:
        return 0.0

    return (option_price / capital_at_risk) * 365 / dte


def calculate_black_scholes_delta(
    spot_price: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float = 0.05,
    volatility: float = 0.30,
    option_type: str = "call",
) -> float:
    """Calculate Black-Scholes delta for an option

    Delta measures the rate of change of option price with respect to stock price.

    Args:
        spot_price: Current stock price (S)
        strike: Strike price (K)
        time_to_expiry: Time to expiry in years (T)
        risk_free_rate: Risk-free interest rate (r), default 5%
        volatility: Implied volatility (σ), default 30%
        option_type: 'call' or 'calls' or 'put' or 'puts'

    Returns:
        Delta value (0 to 1 for calls, -1 to 0 for puts)
    """
    from scipy.stats import norm
    from math import log, sqrt

    if spot_price <= 0 or strike <= 0 or time_to_expiry <= 0:
        return 0.0

    # Calculate d1 from Black-Scholes formula
    d1 = (log(spot_price / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / (
        volatility * sqrt(time_to_expiry)
    )

    # Delta for call: N(d1)
    # Delta for put: N(d1) - 1
    if option_type.lower() in ["call", "calls"]:
        return norm.cdf(d1)
    else:  # put
        return norm.cdf(d1) - 1


def calculate_implied_leverage(
    spot_price: float,
    option_price: float,
    strike: float,
    time_to_expiry: float,
    option_type: str = "call",
    risk_free_rate: float = 0.05,
    volatility: float = 0.30,
) -> float:
    """Calculate implied leverage (Omega) for an option

    Formula: Ω = Δ × (S / O)
    Where:
        Ω (Omega) = Implied leverage
        Δ (Delta) = Option delta from Black-Scholes
        S = Spot price (stock price)
        O = Option price

    This represents the percentage change in option value for a 1% change in stock price.
    For example, if leverage is 10, a 1% move in stock results in ~10% move in option.

    Note: When called from format_options_for_display(), this function requires the actual
    implied volatility from Yahoo Finance API. If implied volatility is not available,
    leverage will be None and displayed as "N/A".

    Args:
        spot_price: Current stock price (S)
        option_price: Current option price (O)
        strike: Strike price (needed for delta calculation)
        time_to_expiry: Time to expiry in years (T)
        option_type: 'call' or 'put'
        risk_free_rate: Risk-free interest rate, default 5%
        volatility: Implied volatility from Yahoo Finance (required for accurate calculation)

    Returns:
        Implied leverage (Omega) as a multiplier
    """
    if option_price <= 0 or spot_price <= 0:
        return 0.0

    # Calculate delta using Black-Scholes
    delta = calculate_black_scholes_delta(spot_price, strike, time_to_expiry, risk_free_rate, volatility, option_type)

    # Omega = Delta × (S / O)
    leverage = abs(delta) * (spot_price / option_price)

    return leverage


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


def evaluate_filter(filter_ast: dict, data: dict) -> bool:
    """Evaluate a filter AST against data.

    Args:
        filter_ast: Parsed filter AST (dict with 'key'/'op'/'value' or 'op'/'children')
        data: Dictionary with data to filter (e.g., {'dte': 30, 'strike': 100})

    Returns:
        True if data passes the filter, False otherwise
    """
    if "key" in filter_ast:
        # Simple filter node
        key = filter_ast["key"]
        op = filter_ast["op"]
        value = filter_ast["value"]

        # Get the data value
        if key not in data:
            return False

        data_value = data[key]

        # Handle None values (e.g., unavailable return metrics)
        if data_value is None:
            if op == "==":
                return value is None
            elif op == "!=":
                return value is not None
            else:
                # None doesn't match other comparisons (>, <, >=, <=)
                return False

        # Evaluate comparison
        if op == ">":
            return data_value > value
        elif op == "<":
            return data_value < value
        elif op == ">=":
            return data_value >= value
        elif op == "<=":
            return data_value <= value
        elif op == "==":
            return data_value == value
        elif op == "!=":
            return data_value != value
        else:
            return False

    elif "op" in filter_ast and "children" in filter_ast:
        # Logical node
        op = filter_ast["op"]
        children = filter_ast["children"]

        if op == "AND":
            return all(evaluate_filter(child, data) for child in children)
        elif op == "OR":
            return any(evaluate_filter(child, data) for child in children)
        else:
            return False

    return False


def format_options_for_display(
    ticker: str,
    option_type: str = "calls",
    sort_by: str = "return",
    max_expiry: str = "6m",
    min_dte: int = None,
    show_all: bool = False,
    filter_ast: dict = None,
):
    """Format options data for fzf-friendly display with enhanced information

    Args:
        ticker: Stock ticker symbol
        option_type: 'calls' or 'puts'
        sort_by: 'strike', 'dte', 'volume', or 'return' (default: 'return')
        max_expiry: Maximum expiry time (e.g., '3m', '6m', '1y'). Default: '6m'
        min_dte: Minimum days to expiry (optional)
        show_all: Show all available expiries (overrides max_expiry)
        filter_ast: Parsed filter AST for advanced filtering (optional)
    """
    from scipy import stats

    options_data = fetch_options_data(ticker)

    if not options_data:
        return []

    # Get spot price for return calculations
    spot_price = get_spot_price(ticker)

    # Filter expiry dates based on max_expiry
    max_days = parse_time_expression(max_expiry)
    filtered_expiry_dates = filter_expiry_dates(options_data.get("expiry_dates", []), max_days, show_all)

    # First pass: collect all options with raw efficiency values
    raw_options = []

    for expiry_date in filtered_expiry_dates:
        if expiry_date not in options_data.get(option_type, {}):
            continue

        options_list = options_data[option_type][expiry_date]
        dte = calculate_days_to_expiry(expiry_date)

        # Apply min_dte filter
        if min_dte is not None and dte < min_dte:
            continue

        for option in options_list:
            strike = option.get("strike", 0)
            volume = option.get("volume", 0) or 0  # Handle None values
            last_price = option.get("lastPrice", 0) or 0
            bid_price = option.get("bid", 0) or 0
            ask_price = option.get("ask", 0) or 0

            # Get last trade date and calculate days since last trade
            last_trade_date = option.get("lastTradeDate", None)
            lt_days = None
            if last_trade_date:
                try:
                    from datetime import datetime, timezone

                    # lastTradeDate can be a timestamp or datetime
                    if isinstance(last_trade_date, (int, float)):
                        last_trade_dt = datetime.fromtimestamp(last_trade_date)
                    else:
                        last_trade_dt = last_trade_date
                    # Convert both to timezone-aware UTC for comparison
                    now_utc = datetime.now(timezone.utc)
                    if last_trade_dt.tzinfo is None:
                        # If last_trade_dt is naive, assume UTC
                        last_trade_dt = last_trade_dt.replace(tzinfo=timezone.utc)
                    lt_days = (now_utc - last_trade_dt).days
                except Exception:
                    lt_days = None

            # Calculate return metric based on option type
            if option_type == "calls" and last_price > 0:
                return_metric = calculate_cagr_to_breakeven(spot_price, strike, last_price, dte)
                return_str = f"{return_metric:.2%}"
            elif option_type == "puts" and last_price > 0:
                return_metric = calculate_put_annualized_return(strike, last_price, dte)
                return_str = f"{return_metric:.2%}"
            else:
                # No valid price for calculation - display N/A and set metric to None
                # None values are handled specially in filter evaluation (see evaluate_filter)
                return_str = "N/A"
                return_metric = None

            # Calculate AR for bid/ask (puts only)
            ar_bid = (
                calculate_put_annualized_return(strike, bid_price, dte)
                if option_type == "puts" and bid_price > 0
                else None
            )
            ar_ask = (
                calculate_put_annualized_return(strike, ask_price, dte)
                if option_type == "puts" and ask_price > 0
                else None
            )

            # Calculate implied leverage using implied volatility from Yahoo Finance
            # Only calculate if implied volatility is available (no default fallback)
            leverage = None
            if last_price > 0 and strike > 0 and dte > 0:
                time_to_expiry_years = dte / 365.0
                # Get implied volatility from Yahoo Finance data
                implied_vol = option.get("impliedVolatility", None)
                if implied_vol and implied_vol > 0:
                    # Use actual market implied volatility
                    leverage = calculate_implied_leverage(
                        spot_price, last_price, strike, time_to_expiry_years, option_type, volatility=implied_vol
                    )
                # If no implied volatility available, leverage remains None (will display as N/A)

            # Calculate strike percentage (% above/below spot)
            strike_pct = None
            if spot_price > 0 and strike > 0:
                strike_pct = ((strike - spot_price) / spot_price) * 100

            # Calculate raw efficiency (leverage / CAGR)
            # Will be converted to percentile in second pass
            raw_efficiency = None
            if leverage and leverage > 0 and return_metric and return_metric > 0:
                raw_efficiency = leverage / return_metric

            # Store option data for first pass
            implied_vol = option.get("impliedVolatility", None)
            raw_options.append(
                {
                    "ticker": ticker,
                    "strike": strike,
                    "dte": dte,
                    "expiry_date": expiry_date,
                    "volume": volume,
                    "price": last_price,
                    "bid": bid_price,
                    "ask": ask_price,
                    "ar_bid": ar_bid,
                    "ar_ask": ar_ask,
                    "iv": implied_vol,
                    "return_metric": return_metric,
                    "return_str": return_str,
                    "leverage": leverage,
                    "strike_pct": strike_pct,
                    "lt_days": lt_days,
                    "raw_efficiency": raw_efficiency,
                    "option_type": option_type,
                }
            )

    # Second pass: calculate efficiency percentiles
    valid_efficiencies = [opt["raw_efficiency"] for opt in raw_options if opt["raw_efficiency"] is not None]

    # Build final formatted options with efficiency percentiles
    formatted_options = []
    for opt in raw_options:
        # Calculate efficiency percentile (0-100)
        efficiency = None
        if opt["raw_efficiency"] is not None and len(valid_efficiencies) > 0:
            efficiency = stats.percentileofscore(valid_efficiencies, opt["raw_efficiency"], kind="rank")

        # Create option data dict for filtering
        # Field aliases: ret/ar for return, sp for strike_pct, lt_days for last trade days, lev for leverage, eff for efficiency
        option_data = {
            "dte": opt["dte"],
            "volume": opt["volume"],
            "price": opt["price"],
            "return": opt["return_metric"],
            "ret": opt["return_metric"],
            "ar": opt["return_metric"],
            "strike_pct": opt["strike_pct"],
            "sp": opt["strike_pct"],
            "lt_days": opt["lt_days"],
            "leverage": opt["leverage"],
            "lev": opt["leverage"],
            "efficiency": efficiency,
            "eff": efficiency,
        }

        # Apply filter_ast if provided
        if filter_ast and not evaluate_filter(filter_ast, option_data):
            continue

        # Store for sorting/display
        option_type_letter = "C" if opt["option_type"] == "calls" else "P"

        if opt["option_type"] == "calls":
            leverage_str = f"{opt['leverage']:.1f}x" if opt["leverage"] and opt["leverage"] > 0 else "N/A"
            efficiency_str = f"{efficiency:.0f}" if efficiency is not None else "N/A"
            formatted_option = (
                f"{opt['ticker'].upper()} {opt['strike']:.0f}{option_type_letter} {opt['dte']}DTE "
                f"(${opt['price']:.2f}, {opt['return_str']}, {leverage_str}, eff:{efficiency_str})"
            )
        else:
            formatted_option = None  # puts use table format

        formatted_options.append(
            {
                "display": formatted_option,
                "strike": opt["strike"],
                "dte": opt["dte"],
                "volume": opt["volume"],
                "price": opt["price"],
                "return_metric": opt["return_metric"],
                "leverage": opt["leverage"],
                "efficiency": efficiency,
                # put-specific fields
                "expiry_date": opt.get("expiry_date"),
                "bid": opt.get("bid", 0),
                "ask": opt.get("ask", 0),
                "ar_bid": opt.get("ar_bid"),
                "ar_ask": opt.get("ar_ask"),
                "lt_days": opt.get("lt_days"),
                "iv": opt.get("iv"),
            }
        )

    # Sort based on the specified criteria
    if sort_by == "strike":
        formatted_options.sort(key=lambda x: x["strike"])
    elif sort_by == "dte":
        formatted_options.sort(key=lambda x: x["dte"])
    elif sort_by == "volume":
        formatted_options.sort(key=lambda x: x["volume"], reverse=True)
    elif sort_by == "return":
        # For calls: ascending (smallest to largest return)
        # For puts: descending (largest to smallest return)
        if option_type == "calls":
            formatted_options.sort(key=lambda x: x["return_metric"] if x["return_metric"] is not None else float("inf"))
        else:  # puts
            formatted_options.sort(
                key=lambda x: x["return_metric"] if x["return_metric"] is not None else float("-inf"), reverse=True
            )
    elif sort_by == "efficiency":
        # Sort by efficiency percentile (highest first)
        formatted_options.sort(key=lambda x: x["efficiency"] if x["efficiency"] is not None else -1, reverse=True)

    # For calls, return display strings
    if option_type == "calls":
        return [option["display"] for option in formatted_options]

    # For puts, build a table
    lines = [f"spot = ${spot_price:.2f}", ""]

    # Table header
    header = f"{'Expiry':<20} {'Strike':>7} {'Breakeven':>16} {'Vol':>6} {'IV':>6} {'LT':>4}  {'AR: ask / bid / last'}"
    lines.append(header)
    lines.append("-" * len(header))

    for opt in formatted_options:
        expiry_dt = datetime.strptime(opt["expiry_date"], "%Y-%m-%d")
        expiry_fmt = f"{expiry_dt.strftime('%d/%b/%y')} ({opt['dte']}d)"

        breakeven = opt["strike"] - opt["price"]
        be_pct = (breakeven / spot_price - 1) * 100 if spot_price > 0 else 0
        be_str = f"${breakeven:.2f} ({be_pct:+.1f}%)"

        vol_str = f"{opt['volume']}" if opt["volume"] else "-"
        iv_str = f"{opt['iv']:.0%}" if opt.get("iv") else "-"
        lt_str = f"{opt['lt_days']}d" if opt["lt_days"] is not None else "-"

        # AR with premium values: ask: $X.XX (YY%) | bid: $X.XX (YY%) | last: $X.XX (YY%)
        def _ar_cell(price, ar):
            if price and price > 0 and ar:
                return f"${price:.2f} ({ar:.0%})"
            return "-"

        ar_ask = _ar_cell(opt["ask"], opt["ar_ask"])
        ar_bid = _ar_cell(opt["bid"], opt["ar_bid"])
        ar_last = _ar_cell(opt["price"], opt["return_metric"])
        ar_str = f"ask: {ar_ask} | bid: {ar_bid} | last: {ar_last}"

        row = f"{expiry_fmt:<20} {opt['strike']:>7.0f} {be_str:>16} {vol_str:>6} {iv_str:>6} {lt_str:>4}  {ar_str}"
        lines.append(row)

    return lines
