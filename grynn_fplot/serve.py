# %%
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
from datetime import datetime

# Import shared functions
from grynn_fplot.core import (
    parse_start_date,
    download_ticker_data,
    normalize_prices,
    calculate_drawdowns,
    calculate_area_under_curve,
    calculate_cagr,
)

# Create FastAPI app with optimizations
app = FastAPI(
    title="Financial Plot API", description="Interactive financial charting API", docs_url="/docs", redoc_url="/redoc"
)

# Add CORS middleware for better browser compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory cache for faster repeated requests
_cache = {}
_cache_max_size = 100
_master_cache = {}  # Cache for 5-year datasets
_cache_ttl_minutes = 15


def get_cache_key(ticker: str, since: str, interval: str) -> str:
    """Generate cache key"""
    return f"{ticker}_{since}_{interval}"


def is_cache_valid(cache_entry) -> bool:
    """Check if cache is still valid"""
    if not cache_entry or "timestamp" not in cache_entry:
        return False

    from datetime import datetime, timedelta

    cache_time = datetime.fromisoformat(cache_entry["timestamp"])
    return datetime.now() - cache_time < timedelta(minutes=_cache_ttl_minutes)


@app.get("/")
def index():
    """Serve the main HTML interface"""
    html_path = Path(__file__).parent / "index.html"
    with open(html_path, "r") as f:
        content = f.read()
    return HTMLResponse(content=content)


def get_from_cache(cache_key: str):
    """Get data from cache if available and not expired"""
    if cache_key in _cache:
        data, timestamp = _cache[cache_key]
        # Cache for 5 minutes for intraday data, 30 minutes for longer periods
        cache_duration = 300 if "d" in cache_key else 1800
        if (datetime.now().timestamp() - timestamp) < cache_duration:
            return data
        else:
            # Remove expired entry
            del _cache[cache_key]
    return None


def set_cache(cache_key: str, data):
    """Store data in cache with size limit"""
    global _cache
    if len(_cache) >= _cache_max_size:
        # Remove oldest entry
        oldest_key = min(_cache.keys(), key=lambda k: _cache[k][1])
        del _cache[oldest_key]

    _cache[cache_key] = (data, datetime.now().timestamp())


@app.get("/data")
async def get_data(ticker: str, since: str = None, interval: str = "1d"):
    """Get financial data for charting with caching for better performance"""
    try:
        # Check cache first
        cache_key = get_cache_key(ticker, since or "max", interval)
        cached_data = get_from_cache(cache_key)
        if cached_data:
            return JSONResponse(content=cached_data)

        since_date = parse_start_date(since)
        print(f"Downloading data for {ticker} since {since_date} with interval {interval}")

        df = download_ticker_data(ticker, since_date, interval)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for ticker: {ticker}")

        # Handle edge case where last row has missing data
        last_row_has_missing_data = df.iloc[-1].isna().any()
        if last_row_has_missing_data:
            df = df.iloc[:-1]  # drop the last row

        df_normalized = normalize_prices(df).ffill()
        df_dd = calculate_drawdowns(df_normalized).ffill()

        # Calculate additional metrics
        df_auc = calculate_area_under_curve(df_dd)

        # Calculate CAGR if time period >= 1 year
        df_days = (df.index[-1] - df.index[0]).days
        cagr_data = None
        if df_days >= 365:
            cagr_data = calculate_cagr(df_normalized).to_dict("records")

        data = {
            "dates": df.index.strftime("%Y-%m-%d").tolist(),
            "price": df_normalized.to_dict(orient="list"),
            "drawdown": df_dd.to_dict(orient="list"),
            "auc": df_auc.to_dict("records"),
            "cagr": cagr_data,
            "period_days": df_days,
            "tickers": df.columns.tolist(),
            "start_date": df.index[0].strftime("%Y-%m-%d"),
            "end_date": df.index[-1].strftime("%Y-%m-%d"),
        }

        # Cache the result for faster subsequent requests
        set_cache(cache_key, data)

        return JSONResponse(content=data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")


@app.get("/export/{format}")
def export_data(format: str, ticker: str, since: str = None, interval: str = "1d"):
    """Export data in various formats"""
    try:
        # Get the data
        data_response = get_data(ticker, since, interval)
        data = json.loads(data_response.body.decode())

        if format.lower() == "csv":
            csv_content = convert_to_csv(data)
            filename = f"{ticker}_{since or 'max'}_{interval}.csv"

            return JSONResponse(
                content={"content": csv_content, "filename": filename}, headers={"Content-Type": "application/json"}
            )

        elif format.lower() == "json":
            filename = f"{ticker}_{since or 'max'}_{interval}.json"
            return JSONResponse(
                content={"content": json.dumps(data, indent=2), "filename": filename},
                headers={"Content-Type": "application/json"},
            )

        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'csv' or 'json'.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting data: {str(e)}")


def convert_to_csv(data):
    """Convert JSON data to CSV format"""
    dates = data["dates"]
    tickers = data["tickers"]

    # Create header
    headers = ["Date"]
    for ticker in tickers:
        headers.extend([f"{ticker}_Price", f"{ticker}_Drawdown"])

    csv_lines = [",".join(headers)]

    # Add data rows
    for i, date in enumerate(dates):
        row = [date]
        for ticker in tickers:
            price = data["price"][ticker][i] if i < len(data["price"][ticker]) else ""
            drawdown = data["drawdown"][ticker][i] if i < len(data["drawdown"][ticker]) else ""
            row.extend([str(price), str(drawdown)])
        csv_lines.append(",".join(row))

    return "\n".join(csv_lines)


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)


# %%
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "serve:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src/grynn_fplot"],
    )
