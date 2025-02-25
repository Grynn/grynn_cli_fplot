# %%
from fastapi import FastAPI
from fastapi.responses import JSONResponse, HTMLResponse
from pathlib import Path

# Import shared functions
from grynn_fplot.core import (
    parse_start_date,
    download_ticker_data,
    normalize_prices,
    calculate_drawdowns,
)

app = FastAPI()


@app.get("/")
def index():
    html_path = Path(__file__).parent / "index.html"
    with open(html_path, "r") as f:
        content = f.read()
    return HTMLResponse(content=content)


@app.get("/data")
def get_data(ticker: str, since: str = None, interval: str = "1d"):
    since_date = parse_start_date(since)
    print(f"Downloading data for {ticker} since {since_date} with interval {interval}")

    df = download_ticker_data(ticker, since_date, interval)
    if df is None or df.empty:
        return JSONResponse(content={"error": "No data found"}, status_code=404)

    df_normalized = normalize_prices(df).ffill()
    df_dd = calculate_drawdowns(df_normalized).ffill()

    data = {
        "dates": df.index.strftime("%Y-%m-%d").tolist(),
        "price": df_normalized.to_dict(orient="list"),
        "drawdown": df_dd.to_dict(orient="list"),
    }

    try:
        resp = JSONResponse(content=data)
    except Exception as e:
        resp = JSONResponse(content={"error": str(e)}, status_code=500)

    return resp


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
