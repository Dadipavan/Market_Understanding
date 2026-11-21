import numpy as np
import pandas as pd
import pytest

from core.demo import demo_prices
from indicators.technical import add_indicators, atr, bollinger, ema, macd, rsi, sma, support_resistance


def test_sma_known_values():
    s = pd.Series(range(1, 11), dtype=float)
    out = sma(s, 3)
    assert out.iloc[:2].isna().all()
    assert out.iloc[2] == pytest.approx(2.0)
    assert out.iloc[-1] == pytest.approx(9.0)


def test_ema_known_values():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    out = ema(s, 3)  # alpha = 0.5
    assert out.iloc[:2].isna().all()
    assert out.iloc[2] == pytest.approx(2.25)
    assert out.iloc[3] == pytest.approx(3.125)
    assert out.iloc[4] == pytest.approx(4.0625)


def test_rsi_bounded_and_extremes():
    out = rsi(demo_prices("TEST", "2y")["Close"]).dropna()
    assert len(out) > 400
    assert out.between(0, 100).all()
    assert rsi(pd.Series(np.arange(1, 60, dtype=float))).iloc[-1] == pytest.approx(100.0)
    assert rsi(pd.Series(np.arange(60, 1, -1, dtype=float))).iloc[-1] == pytest.approx(0.0, abs=1e-6)


def test_atr_constant_range():
    n = 40
    df = pd.DataFrame({"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1}, index=pd.RangeIndex(n))
    out = atr(df, 14).dropna()
    assert out.iloc[-1] == pytest.approx(2.0)


def test_macd_columns_and_constant_series():
    out = macd(pd.Series([50.0] * 80))
    assert list(out.columns) == ["MACD", "MACD_signal", "MACD_hist"]
    assert out.dropna().abs().max().max() == pytest.approx(0.0, abs=1e-9)
    c = demo_prices("MACD", "1y")["Close"]
    m = macd(c).dropna()
    assert (m["MACD_hist"] - (m["MACD"] - m["MACD_signal"])).abs().max() < 1e-9


def test_bollinger_ordering():
    b = bollinger(demo_prices("BB", "1y")["Close"]).dropna()
    assert (b["BB_up"] >= b["BB_mid"]).all() and (b["BB_mid"] >= b["BB_low"]).all()


def test_add_indicators_columns():
    d = add_indicators(demo_prices("X", "2y"))
    for col in ["SMA20", "EMA50", "EMA200", "RSI", "MACD", "MACD_signal", "MACD_hist", "ATR", "BB_up", "BB_low", "VolAvg5", "VolAvg20"]:
        assert col in d.columns
    assert d["EMA200"].notna().sum() > 0


def test_support_resistance_wave():
    x = np.arange(200)
    close = 100 + 10 * np.sin(x / 8.0)
    df = pd.DataFrame({"Open": close, "High": close + 0.5, "Low": close - 0.5, "Close": close, "Volume": 1.0},
                      index=pd.bdate_range("2025-01-01", periods=200))
    sup, res = support_resistance(df)
    last = float(df["Close"].iloc[-1])
    assert sup is not None and res is not None
    assert sup < last < res
    assert sup > 85 and res < 115


def test_support_resistance_short_data():
    assert support_resistance(demo_prices("S", "1mo").head(5)) == (None, None)
