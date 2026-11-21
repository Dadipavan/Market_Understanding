import numpy as np
import pandas as pd
import pytest

from funds import amfi, analytics
from funds.amfi import demo_nav, parse_mfapi, parse_navall

NAVALL = """Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

Axis Mutual Fund
119551;INF846K01DP8;-;Axis Bluechip Fund - Direct Plan - Growth;50.12;21-Nov-2026
119552;-;-;Broken Fund;N.A.;21-Nov-2026
119553;-;-;HDFC Top 100 - Growth;1,000.5;21-Nov-2026
"""


def daily_growth(rate: float, years: float, start: float = 100.0) -> pd.Series:
    idx = pd.date_range("2018-01-01", periods=int(years * 365.25) + 1, freq="D")
    t = np.arange(len(idx)) / 365.25
    return pd.Series(start * (1 + rate) ** t, index=idx)


def test_parse_navall():
    df = parse_navall(NAVALL)
    assert list(df["code"]) == ["119551"]  # "N.A." and thousands-separated NAVs are rejected, not guessed
    assert df.iloc[0]["name"].startswith("Axis Bluechip") and df.iloc[0]["nav"] == pytest.approx(50.12)
    assert "119552" not in set(df["code"])  # N.A. NAV dropped


def test_parse_mfapi():
    s = parse_mfapi({"meta": {}, "data": [{"date": "21-11-2026", "nav": "12.5"}, {"date": "20-11-2026", "nav": "12.0"},
                                            {"date": "garbage", "nav": "1"}, {"date": "19-11-2026", "nav": "x"}]})
    assert list(s.values) == [12.0, 12.5]
    assert s.index.is_monotonic_increasing and s.index[0] == pd.Timestamp("2026-11-20")
    assert parse_mfapi({}).empty


def test_cagr_known_growth():
    nav = daily_growth(0.10, 6)
    assert analytics.cagr(nav, 1) == pytest.approx(0.10, abs=0.005)
    assert analytics.cagr(nav, 3) == pytest.approx(0.10, abs=0.005)
    assert analytics.cagr(nav, 5) == pytest.approx(0.10, abs=0.005)
    assert analytics.cagr(daily_growth(0.10, 2), 5) is None


def test_max_drawdown():
    assert analytics.max_drawdown(pd.Series([100, 120, 90, 110.0])) == pytest.approx(-0.25)
    assert analytics.max_drawdown(pd.Series([1, 2, 3.0])) == 0.0


def test_rolling_returns():
    nav = pd.Series(np.arange(1, 600, dtype=float))
    r = analytics.rolling_returns(nav, 1)
    assert len(r) == len(nav) - 252 and (r > 0).all()


def test_sip_future_value():
    r = (1.12) ** (1 / 12) - 1
    n = 120
    expected = 10_000 * (((1 + r) ** n - 1) / r) * (1 + r)
    out = analytics.sip_future_value(10_000, 10, 0.12)
    assert out["future_value"] == pytest.approx(expected) and out["invested"] == 1_200_000
    assert out["gain"] == pytest.approx(expected - 1_200_000)
    z = analytics.sip_future_value(10_000, 10, 0.0)
    assert z["future_value"] == pytest.approx(1_200_000)


def test_xirr():
    cfs = [(pd.Timestamp("2021-01-01"), -1000.0), (pd.Timestamp("2022-01-01"), 1100.0)]
    assert analytics.xirr(cfs) == pytest.approx(0.10, abs=1e-4)
    assert analytics.xirr([(pd.Timestamp("2021-01-01"), -1000.0)]) is None
    assert analytics.xirr([]) is None


def test_sip_backtest_flat_and_growing():
    flat = pd.Series(100.0, index=pd.date_range("2022-01-01", periods=365 * 4, freq="D"))
    r = analytics.sip_backtest(flat, 5_000, 3)
    assert 36 <= r["installments"] <= 37
    assert r["value"] == pytest.approx(r["invested"]) and abs(r["xirr"]) < 1e-3
    g = analytics.sip_backtest(daily_growth(0.12, 5), 5_000, 3)
    assert g["value"] > g["invested"] and g["xirr"] == pytest.approx(0.12, abs=0.02)
    assert analytics.sip_backtest(flat.head(5), 5_000, 3) is None


def test_fund_metrics_and_analysis():
    nav = demo_nav("900001")
    m = analytics.fund_metrics(nav)
    assert m["history_years"] > 6 and m["cagr_5y"] is not None
    assert -1 <= m["max_drawdown"] <= 0 and m["volatility"] > 0
    a, cov = analytics.fund_analysis(m)
    assert 0 <= a.score <= 100 and cov == pytest.approx(1.0) and a.verdict in {"Strong", "Average", "Weak"}
    short = analytics.fund_metrics(nav.tail(300))
    a2, cov2 = analytics.fund_analysis(short)
    assert short["cagr_3y"] is None and cov2 < 1
    assert not [r for r in a2.reasons if r.rule == "3-year return"][0].available


def test_expense_drag():
    d = analytics.expense_drag(10_000, 20, 0.12, 0.005, 0.015)
    assert d["low_cost_value"] > d["high_cost_value"] and d["difference"] > 0


def test_demo_helpers():
    assert len(amfi.demo_schemes()) == 3
    assert demo_nav("900002").equals(demo_nav("900002"))
