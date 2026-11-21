"""Deterministic synthetic data for demos and offline tests. NEVER real prices."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

PERIOD_DAYS = {"1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "2y": 504, "5y": 1260, "10y": 2520, "max": 2520}


def _seed(symbol: str) -> int:
    return int(hashlib.sha1(symbol.encode()).hexdigest()[:8], 16)


def demo_prices(symbol: str, period: str = "1y") -> pd.DataFrame:
    n = PERIOD_DAYS.get(period, 252)
    seed = _seed(symbol)
    rng = np.random.default_rng(seed)
    drift = 0.0002 + (seed % 7) * 0.00015
    rets = rng.normal(drift, 0.014, n)
    base = 100 + seed % 2900
    close = base * np.cumprod(1 + rets)
    prev = np.concatenate([[base], close[:-1]])
    open_ = prev * (1 + rng.normal(0, 0.003, n))
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.005, n)))
    vol = rng.integers(200_000, 5_000_000, n)
    idx = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=n)
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol}, index=idx)


def demo_fundamentals(symbol: str) -> dict:
    rng = np.random.default_rng(_seed(symbol) + 1)
    sectors = ["Technology", "Financial Services", "Energy", "Consumer Defensive", "Healthcare", "Industrials"]
    sector = sectors[_seed(symbol) % len(sectors)]
    return {
        "name": f"{symbol} (DEMO)",
        "sector": sector,
        "industry": "Demo industry",
        "market_cap": float(rng.uniform(5e10, 2e12)),
        "pe": float(rng.uniform(8, 55)),
        "pb": float(rng.uniform(1, 9)),
        "roe": float(rng.uniform(0.04, 0.30)),
        "debt_to_equity": float(rng.uniform(0.05, 2.0)),
        "profit_margin": float(rng.uniform(0.02, 0.28)),
        "operating_margin": float(rng.uniform(0.05, 0.35)),
        "revenue_growth": float(rng.uniform(-0.05, 0.30)),
        "earnings_growth": float(rng.uniform(-0.10, 0.40)),
        "current_ratio": float(rng.uniform(0.7, 2.5)),
        "promoter_holding": float(rng.uniform(0.15, 0.75)),
        "dividend_yield": float(rng.uniform(0, 0.03)),
        "beta": float(rng.uniform(0.6, 1.6)),
        "source": "DEMO (synthetic)",
    }
