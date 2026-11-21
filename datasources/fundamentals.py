"""Company fundamentals from yfinance, normalised into one plain dict.

Free fundamentals for Indian companies are patchy: missing values are kept as
None and the scoring layer treats them as 'not available' (never as zero).
"""
from __future__ import annotations

import yfinance as yf

from core import cache
from core.demo import demo_fundamentals
from datasources.yahoo import DataSourceError
from markets.india import MARKET

TTL = 6 * 3600


def _f(v):
    try:
        if v is None:
            return None
        v = float(v)
        return None if v != v else v  # drop NaN
    except (TypeError, ValueError):
        return None


def normalise(info: dict) -> dict:
    price = _f(info.get("currentPrice")) or _f(info.get("regularMarketPrice"))
    div_rate = _f(info.get("dividendRate"))
    dte = _f(info.get("debtToEquity"))
    return {
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": _f(info.get("marketCap")),
        "pe": _f(info.get("trailingPE")),
        "pb": _f(info.get("priceToBook")),
        "roe": _f(info.get("returnOnEquity")),
        "debt_to_equity": dte / 100 if dte is not None else None,  # yfinance reports percent
        "profit_margin": _f(info.get("profitMargins")),
        "operating_margin": _f(info.get("operatingMargins")),
        "revenue_growth": _f(info.get("revenueGrowth")),
        "earnings_growth": _f(info.get("earningsGrowth")),
        "current_ratio": _f(info.get("currentRatio")),
        "promoter_holding": _f(info.get("heldPercentInsiders")),
        "dividend_yield": (div_rate / price) if (div_rate and price) else None,
        "beta": _f(info.get("beta")),
        "source": "Yahoo Finance (yfinance) - verify on Screener.in / company filings",
    }


def get_fundamentals(symbol: str, demo: bool = False) -> dict:
    if demo:
        return demo_fundamentals(symbol)
    ysym = MARKET.to_yahoo(symbol)
    key = f"fund:{ysym}"
    hit = cache.get(key, TTL)
    if hit is not None:
        return hit
    try:
        info = yf.Ticker(ysym).info or {}
    except Exception as e:
        raise DataSourceError(f"Fundamentals unavailable: {type(e).__name__}") from e
    data = normalise(info)
    if all(v is None for k, v in data.items() if k not in ("source",)):
        return {}
    cache.put(key, data)
    return data
