"""Standard technical indicators in plain pandas (no TA library needed)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder's RSI."""
    d = close.diff()
    gain = d.clip(lower=0)
    loss = -d.clip(upper=0)
    ag = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    al = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = ag / al.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.mask(al.eq(0) & ag.gt(0), 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = close.ewm(span=fast, adjust=False, min_periods=fast).mean() - close.ewm(span=slow, adjust=False, min_periods=slow).mean()
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"MACD": line, "MACD_signal": sig, "MACD_hist": line - sig})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    sd = close.rolling(n, min_periods=n).std()
    return pd.DataFrame({"BB_mid": mid, "BB_up": mid + k * sd, "BB_low": mid - k * sd})


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    c = out["Close"]
    out["SMA20"] = sma(c, 20)
    out["EMA50"] = ema(c, 50)
    out["EMA200"] = ema(c, 200)
    out["RSI"] = rsi(c)
    out = out.join(macd(c))
    out["ATR"] = atr(out)
    out = out.join(bollinger(c))
    out["VolAvg5"] = out["Volume"].rolling(5, min_periods=5).mean()
    out["VolAvg20"] = out["Volume"].rolling(20, min_periods=20).mean()
    return out


def support_resistance(df: pd.DataFrame, window: int = 5, lookback: int = 150) -> tuple[float | None, float | None]:
    """Nearest swing-low support below and swing-high resistance above the last close."""
    d = df.tail(lookback)
    if len(d) < window * 2 + 1:
        return None, None
    w = window * 2 + 1
    swing_low = d["Low"][d["Low"] == d["Low"].rolling(w, center=True).min()]
    swing_high = d["High"][d["High"] == d["High"].rolling(w, center=True).max()]
    last = float(d["Close"].iloc[-1])
    below = swing_low[swing_low < last]
    above = swing_high[swing_high > last]
    return (float(below.iloc[-1]) if not below.empty else None, float(above.iloc[-1]) if not above.empty else None)
