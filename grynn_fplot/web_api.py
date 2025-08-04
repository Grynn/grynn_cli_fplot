"""
Enhanced interactive web interface for financial plotting
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import shared functions
from grynn_fplot.core import (
    parse_start_date,
    download_ticker_data,
    normalize_prices,
    calculate_drawdowns,
    calculate_area_under_curve,
    calculate_cagr,
)

app = FastAPI(
    title="Financial Plot API", description="Interactive financial charting API with advanced features", version="2.0.0"
)


@app.get("/")
def index():
    """Serve the main HTML interface"""
    html_path = Path(__file__).parent / "index.html"
    with open(html_path, "r") as f:
        content = f.read()
    return HTMLResponse(content=content)


@app.get("/api/data")
def get_data(ticker: str, since: str = None, interval: str = "1d", indicators: Optional[str] = None):
    """Get financial data for charting with optional technical indicators"""
    try:
        since_date = parse_start_date(since)
        print(f"Downloading data for {ticker} since {since_date} with interval {interval}")

        df = download_ticker_data(ticker, since_date, interval)
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for ticker: {ticker}")

        # Handle edge case where last row has missing data
        last_row_has_missing_data = df.iloc[-1].isna().any()
        if last_row_has_missing_data:
            df = df.iloc[:-1]

        df_normalized = normalize_prices(df).ffill()
        df_dd = calculate_drawdowns(df_normalized).ffill()

        # Calculate additional metrics
        df_auc = calculate_area_under_curve(df_dd)

        # Calculate CAGR if time period >= 1 year
        df_days = (df.index[-1] - df.index[0]).days
        cagr_data = None
        if df_days >= 365:
            cagr_data = calculate_cagr(df_normalized).to_dict("records")

        # Add technical indicators if requested
        indicators_data = {}
        if indicators:
            indicator_list = indicators.split(",")
            indicators_data = calculate_technical_indicators(df, indicator_list)

        data = {
            "dates": df.index.strftime("%Y-%m-%d").tolist(),
            "price": df_normalized.to_dict(orient="list"),
            "drawdown": df_dd.to_dict(orient="list"),
            "raw_price": df.to_dict(orient="list"),
            "auc": df_auc.to_dict("records"),
            "cagr": cagr_data,
            "indicators": indicators_data,
            "period_days": df_days,
            "tickers": df.columns.tolist(),
            "start_date": df.index[0].strftime("%Y-%m-%d"),
            "end_date": df.index[-1].strftime("%Y-%m-%d"),
            "total_return": {
                ticker: float(
                    ((df_normalized[ticker].iloc[-1] - df_normalized[ticker].iloc[0]) / df_normalized[ticker].iloc[0])
                    * 100
                )
                for ticker in df.columns
            },
        }

        return JSONResponse(content=data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")


def calculate_technical_indicators(df, indicators: List[str]) -> Dict[str, Any]:
    """Calculate technical indicators for the data"""

    results = {}

    for indicator in indicators:
        indicator = indicator.strip().lower()

        if indicator.startswith("ma_"):
            # Moving average
            period = int(indicator.split("_")[1])
            for ticker in df.columns:
                ma_key = f"{ticker}_MA_{period}"
                results[ma_key] = df[ticker].rolling(window=period).mean().tolist()

        elif indicator == "rsi":
            # RSI calculation (simplified)
            for ticker in df.columns:
                rsi_key = f"{ticker}_RSI"
                results[rsi_key] = calculate_rsi(df[ticker]).tolist()

        elif indicator == "macd":
            # MACD calculation (simplified)
            for ticker in df.columns:
                macd_data = calculate_macd(df[ticker])
                results[f"{ticker}_MACD"] = macd_data["macd"].tolist()
                results[f"{ticker}_MACD_signal"] = macd_data["signal"].tolist()
                results[f"{ticker}_MACD_histogram"] = macd_data["histogram"].tolist()

    return results


def calculate_rsi(price_series, period=14):
    """Calculate RSI indicator"""

    delta = price_series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def calculate_macd(price_series, fast=12, slow=26, signal=9):
    """Calculate MACD indicator"""

    ema_fast = price_series.ewm(span=fast).mean()
    ema_slow = price_series.ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal).mean()
    histogram = macd - signal_line

    return {"macd": macd.fillna(0), "signal": signal_line.fillna(0), "histogram": histogram.fillna(0)}


@app.get("/api/export/{format}")
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
        headers.extend([f"{ticker}_Price", f"{ticker}_Drawdown", f"{ticker}_Raw_Price"])

    # Add indicator headers
    for indicator_key in data["indicators"].keys():
        headers.append(indicator_key)

    csv_lines = [",".join(headers)]

    # Add data rows
    for i, date in enumerate(dates):
        row = [date]
        for ticker in tickers:
            price = data["price"][ticker][i] if i < len(data["price"][ticker]) else ""
            drawdown = data["drawdown"][ticker][i] if i < len(data["drawdown"][ticker]) else ""
            raw_price = data["raw_price"][ticker][i] if i < len(data["raw_price"][ticker]) else ""
            row.extend([str(price), str(drawdown), str(raw_price)])

        # Add indicator values
        for indicator_key, indicator_values in data["indicators"].items():
            value = indicator_values[i] if i < len(indicator_values) else ""
            row.append(str(value))

        csv_lines.append(",".join(row))

    return "\n".join(csv_lines)


@app.get("/api/compare")
def compare_tickers(tickers: str, since: str = None, interval: str = "1d"):
    """Compare multiple tickers side by side"""
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]

        all_data = {}
        for ticker in ticker_list:
            try:
                ticker_data = get_data(ticker, since, interval)
                ticker_json = json.loads(ticker_data.body.decode())
                all_data[ticker] = ticker_json
            except Exception as e:
                print(f"Error fetching data for {ticker}: {e}")
                continue

        if not all_data:
            raise HTTPException(status_code=404, detail="No data found for any of the provided tickers")

        # Combine data for comparison
        combined_data = {"tickers": list(all_data.keys()), "comparison": {}, "performance": {}}

        for ticker, data in all_data.items():
            combined_data["comparison"][ticker] = {
                "total_return": data["total_return"][ticker],
                "max_drawdown": min([min(dd_values) for dd_values in data["drawdown"].values()]),
                "cagr": data["cagr"][0]["CAGR"] if data["cagr"] else None,
                "period_days": data["period_days"],
            }

        return JSONResponse(content=combined_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing tickers: {str(e)}")


@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "version": "2.0.0"}


@app.get("/api/config")
def get_config():
    """Get configuration for the frontend"""
    return {
        "timeRanges": [
            {"label": "1M", "value": "1m"},
            {"label": "3M", "value": "3m"},
            {"label": "6M", "value": "6m"},
            {"label": "1Y", "value": "1y"},
            {"label": "2Y", "value": "2y"},
            {"label": "5Y", "value": "5y"},
            {"label": "MAX", "value": "max"},
        ],
        "intervals": [
            {"label": "1D", "value": "1d"},
            {"label": "1W", "value": "1wk"},
            {"label": "1M", "value": "1mo"},
        ],
        "indicators": [
            {"label": "MA 20", "value": "ma_20"},
            {"label": "MA 50", "value": "ma_50"},
            {"label": "MA 200", "value": "ma_200"},
            {"label": "RSI", "value": "rsi"},
            {"label": "MACD", "value": "macd"},
        ],
        "themes": ["dark", "light", "tradingview"],
        "exportFormats": ["csv", "json"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
