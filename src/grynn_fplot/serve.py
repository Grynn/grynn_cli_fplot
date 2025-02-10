from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

# Import shared functions
from grynn_fplot.core import (
    parse_start_date,
    download_ticker_data,
    normalize_prices,
    calculate_drawdowns,
)

app = FastAPI()

@app.get("/")
def get_data(request: Request, ticker: str, since: str = None, interval: str = "1d"):
    since_date = parse_start_date(since)
    df = download_ticker_data(ticker, since_date, interval)
    if df is None or df.empty:
        return JSONResponse(content={"error": "No data found"}, status_code=404)

    df_normalized = normalize_prices(df)
    df_dd = calculate_drawdowns(df_normalized)
    data = {
        "dates": df.index.strftime('%Y-%m-%d').tolist(),
        "price": df_normalized.to_dict(orient='list'),
        "drawdown": df_dd.to_dict(orient='list'),
    }
    return JSONResponse(content=data)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("serve:app", host="0.0.0.0", port=8000)
