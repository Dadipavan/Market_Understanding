"""One entry point for price data: fetch, validate, cross-check, timestamp."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.demo import demo_prices
from core.validation import Check, cross_check, validate_ohlcv
from datasources import nse, yahoo
from datasources.yahoo import DataSourceError
from markets.india import MARKET


@dataclass
class PriceResult:
    symbol: str
    df: pd.DataFrame
    checks: list[Check] = field(default_factory=list)
    as_of: str = ""
    sources: list[str] = field(default_factory=list)
    demo: bool = False

    @property
    def verified(self) -> bool:
        return bool(self.checks) and all(c.ok for c in self.checks)


def get_prices(symbol: str, period: str = "1y", tolerance: float = 0.01, demo: bool = False,
               raw: bool = False, cross_verify: bool = True) -> PriceResult:
    """raw=True uses the symbol as-is on Yahoo (gold, crypto, indices) with no NSE cross-check."""
    if demo:
        df = demo_prices(symbol, period)
        res = PriceResult(symbol=symbol, df=df, sources=["DEMO (synthetic data, not real prices)"], demo=True)
        res.checks = validate_ohlcv(df)
        res.as_of = f"{df.index[-1]:%Y-%m-%d}"
        return res

    ysym = symbol if raw else MARKET.to_yahoo(symbol)
    try:
        df = yahoo.fetch_history(ysym, period)
    except DataSourceError as e:
        return PriceResult(symbol=symbol, df=pd.DataFrame(), checks=[Check("data source reachable", False, str(e))])
    result = PriceResult(symbol=symbol, df=df, sources=["Yahoo Finance (yfinance)"])
    result.checks = validate_ohlcv(df)
    if df.empty:
        return result
    result.as_of = f"{df.index[-1]:%Y-%m-%d}"

    nse_listed = not raw and not ysym.startswith("^") and ysym.endswith(".NS")
    if cross_verify and nse_listed:
        latest = nse.latest_bhavcopy()
        if latest is None:
            result.checks.append(Check("two-source price match", False, "NSE bhavcopy unavailable - cannot cross-verify"))
        else:
            nse_day, bhav = latest
            base = MARKET.from_yahoo(ysym)
            norm = df.index.tz_localize(None).normalize() if df.index.tz is not None else df.index.normalize()
            mask = norm == pd.Timestamp(nse_day)
            if base in bhav.index and mask.any():
                y_close = float(df.loc[mask, "Close"].iloc[-1])
                result.checks.append(cross_check("Yahoo", y_close, "NSE", float(bhav.loc[base, "Close"]), tolerance))
                result.sources.append(f"NSE bhavcopy ({nse_day:%Y-%m-%d})")
            else:
                result.checks.append(Check("two-source price match", False, f"{base} not found in NSE data for {nse_day}"))
    return result
