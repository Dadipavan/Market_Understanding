"""Yahoo Finance via yfinance. Free and unofficial: good for prototyping,
cross-checked against NSE before display."""
from __future__ import annotations

import pandas as pd
import yfinance as yf

from core import cache

TTL = 15 * 60  # 15 minutes


class DataSourceError(Exception):
    """A data source could not be reached or returned unusable data."""


def fetch_history(yahoo_symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    key = f"yahoo:{yahoo_symbol}:{period}:{interval}"
    hit = cache.get(key, TTL)
    if hit is not None:
        return hit
    # auto_adjust=False keeps raw closes, which is what NSE reports.
    try:
        df = yf.Ticker(yahoo_symbol).history(period=period, interval=interval, auto_adjust=False)
    except Exception as e:  # network/DNS/rate-limit: surface a clean error, not a crash
        raise DataSourceError(f"Yahoo Finance unreachable: {type(e).__name__}") from e
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index)
    cache.put(key, df)
    return df


def fetch_many(yahoo_symbols: list[str], period: str = "1y") -> dict[str, pd.DataFrame]:
    """Batch download for the screener. Symbols that fail are simply missing from the result."""
    out: dict[str, pd.DataFrame] = {}
    todo = []
    for s in yahoo_symbols:
        hit = cache.get(f"yahoo:{s}:{period}:1d", TTL)
        if hit is not None:
            out[s] = hit
        else:
            todo.append(s)
    if not todo:
        return out
    try:
        data = yf.download(todo, period=period, interval="1d", auto_adjust=False,
                           group_by="ticker", threads=True, progress=False)
    except Exception as e:
        raise DataSourceError(f"Yahoo Finance unreachable: {type(e).__name__}") from e
    for s in todo:
        try:
            df = data[s] if len(todo) > 1 else data
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
            if not df.empty:
                df.index = pd.to_datetime(df.index)
                cache.put(f"yahoo:{s}:{period}:1d", df)
                out[s] = df
        except Exception:
            continue
    return out
