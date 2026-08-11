"""Download and prepare the data used by the CAPM project."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests
import yfinance as yf
from pandas_datareader import data as web


START_DATE = "2016-01-01"
END_DATE = "2026-01-01"  # yfinance uses an exclusive end date.

STOCKS = {
    "AAPL": "Information Technology",
    "JPM": "Financials",
    "JNJ": "Health Care",
    "XOM": "Energy",
    "PG": "Consumer Staples",
    "CAT": "Industrials",
    "NEE": "Utilities",
    "AMZN": "Consumer Discretionary",
    "LIN": "Materials",
    "PLD": "Real Estate",
}
MARKET_TICKER = "^GSPC"
RISK_FREE_SERIES = "DGS3MO"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
YFINANCE_CACHE_DIR = PROJECT_ROOT / "data" / ".yfinance-cache"


def download_adjusted_prices(tickers: list[str]) -> pd.DataFrame:
    """Download split- and dividend-adjusted daily closing prices."""
    YFINANCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))
    prices = yf.download(
        tickers=tickers,
        start=START_DATE,
        end=END_DATE,
        auto_adjust=True,
        progress=False,
        group_by="column",
        # A single batch request is slower but avoids Yahoo throttling and
        # concurrent access to yfinance's cookie database.
        threads=False,
    )
    if prices.empty:
        return download_prices_from_yahoo_chart(tickers)

    close = prices["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(name=tickers[0])
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close.sort_index().reindex(columns=tickers)
    if any(close[ticker].isna().all() for ticker in tickers):
        return download_prices_from_yahoo_chart(tickers)
    return close


def download_prices_from_yahoo_chart(tickers: list[str]) -> pd.DataFrame:
    """Fallback to Yahoo's chart endpoint when yfinance is rate limited."""
    period1 = int(pd.Timestamp(START_DATE, tz="UTC").timestamp())
    period2 = int(pd.Timestamp(END_DATE, tz="UTC").timestamp())
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 CAPM research project"})
    series: list[pd.Series] = []

    for ticker in tickers:
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}"
        response = session.get(
            url,
            params={
                "period1": period1,
                "period2": period2,
                "interval": "1d",
                "events": "div,splits",
            },
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        timestamps = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(None)
        adjusted = result["indicators"]["adjclose"][0]["adjclose"]
        series.append(pd.Series(adjusted, index=timestamps, name=ticker, dtype="float64"))

    prices = pd.concat(series, axis=1).sort_index()
    prices.index = prices.index.normalize()
    prices.index.name = "Date"
    return prices.reindex(columns=tickers)


def download_risk_free_rate() -> pd.DataFrame:
    """Download the annualized 3-month Treasury rate from FRED."""
    risk_free = web.DataReader(
        RISK_FREE_SERIES,
        "fred",
        START_DATE,
        "2025-12-31",
    )
    risk_free.index = pd.to_datetime(risk_free.index)
    risk_free.index.name = "Date"
    return risk_free.rename(columns={RISK_FREE_SERIES: "rf_annual_pct"})


def build_processed_data(
    stock_prices: pd.DataFrame,
    market_prices: pd.DataFrame,
    risk_free: pd.DataFrame,
) -> pd.DataFrame:
    """Align trading dates and calculate daily and excess returns."""
    stock_returns = stock_prices.pct_change(fill_method=None)
    stock_returns.columns = [f"{ticker}_return" for ticker in stock_returns]

    market_returns = market_prices.pct_change(fill_method=None)
    market_returns.columns = ["market_return"]

    combined = stock_returns.join(market_returns, how="inner")
    combined = combined.join(risk_free, how="left")
    combined["rf_annual_pct"] = combined["rf_annual_pct"].ffill()
    combined["rf_daily"] = (1 + combined["rf_annual_pct"] / 100) ** (1 / 252) - 1
    combined["market_excess"] = combined["market_return"] - combined["rf_daily"]

    for ticker in STOCKS:
        combined[f"{ticker}_excess"] = (
            combined[f"{ticker}_return"] - combined["rf_daily"]
        )

    required = [f"{ticker}_return" for ticker in STOCKS] + ["market_return", "rf_daily"]
    return combined.dropna(subset=required).sort_index()


def validate_data(
    stock_prices: pd.DataFrame,
    market_prices: pd.DataFrame,
    processed: pd.DataFrame,
) -> None:
    """Fail loudly if a download is incomplete or unsuitable for regression."""
    missing_tickers = [ticker for ticker in STOCKS if stock_prices[ticker].isna().all()]
    if missing_tickers:
        raise ValueError(f"No observations downloaded for: {missing_tickers}")
    if market_prices[MARKET_TICKER].isna().all():
        raise ValueError("No S&P 500 observations downloaded.")
    if processed.empty:
        raise ValueError("Processed dataset is empty after date alignment.")
    if processed.index.has_duplicates:
        raise ValueError("Processed dataset contains duplicate dates.")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    all_prices = download_adjusted_prices([*STOCKS, MARKET_TICKER])
    stock_prices = all_prices[list(STOCKS)].copy()
    market_prices = all_prices[[MARKET_TICKER]].copy()
    risk_free = download_risk_free_rate()
    processed = build_processed_data(stock_prices, market_prices, risk_free)
    validate_data(stock_prices, market_prices, processed)

    stock_prices.index.name = "Date"
    market_prices.index.name = "Date"
    processed.index.name = "Date"

    stock_prices.to_csv(RAW_DIR / "stock_prices.csv")
    market_prices.to_csv(RAW_DIR / "market_prices.csv")
    risk_free.to_csv(RAW_DIR / "risk_free_rate.csv")
    processed.to_csv(PROCESSED_DIR / "capm_daily_data.csv")

    metadata = {
        "start_date": START_DATE,
        "end_date_inclusive": "2025-12-31",
        "frequency": "daily",
        "price_type": "adjusted close",
        "price_source": "Yahoo Finance",
        "stocks": STOCKS,
        "market_ticker": MARKET_TICKER,
        "risk_free_series": RISK_FREE_SERIES,
        "risk_free_source": "FRED",
        "trading_days_per_year": 252,
    }
    (RAW_DIR / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    print(f"Stock prices: {stock_prices.shape}, {stock_prices.index.min().date()} to {stock_prices.index.max().date()}")
    print(f"Market prices: {market_prices.shape}, {market_prices.index.min().date()} to {market_prices.index.max().date()}")
    print(f"Risk-free rate: {risk_free.shape}, {risk_free.index.min().date()} to {risk_free.index.max().date()}")
    print(f"Processed data: {processed.shape}, {processed.index.min().date()} to {processed.index.max().date()}")
    print(f"Saved raw data to: {RAW_DIR}")
    print(f"Saved processed data to: {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
