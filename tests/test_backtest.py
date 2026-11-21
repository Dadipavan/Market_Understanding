import numpy as np
import pandas as pd
import pytest

from backtest import engine
from backtest.engine import STRATEGIES, run_backtest
from core.demo import demo_prices


def test_all_strategies_run():
    df = demo_prices("BT", "5y")
    for name in STRATEGIES:
        r = run_backtest(df, name)
        assert len(r.equity) == len(df)
        assert set(["total_return", "cagr", "max_drawdown", "sharpe", "trades", "win_rate", "exposure"]) <= set(r.metrics)
        assert -1 <= r.metrics["max_drawdown"] <= 0
        assert 0 <= r.metrics["exposure"] <= 1


def test_benchmark_equals_price_ratio():
    df = demo_prices("BH", "2y")
    r = run_backtest(df, "EMA 20/50 crossover", initial=100_000)
    assert r.benchmark.iloc[0] == pytest.approx(100_000)
    assert r.benchmark.iloc[-1] / r.benchmark.iloc[0] == pytest.approx(df["Close"].iloc[-1] / df["Close"].iloc[0])
    assert r.metrics["bh_total_return"] == pytest.approx(df["Close"].iloc[-1] / df["Close"].iloc[0] - 1)


def test_no_lookahead_signal_acts_next_bar(monkeypatch):
    n = 100
    close = np.full(n, 100.0)
    close[40:] = 110.0  # +10% jump on bar 40, flat afterwards
    df = pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0},
                      index=pd.bdate_range("2025-01-01", periods=n))
    sig = pd.Series(0, index=df.index)
    sig.iloc[40] = 1  # signal appears ON the jump bar: it is too late to capture it

    monkeypatch.setattr(engine, "signal", lambda d, name: sig)
    r = run_backtest(df, "EMA 20/50 crossover", cost_pct=0.0, initial=100_000)
    assert r.equity.iloc[-1] == pytest.approx(100_000)  # jump not captured


def test_signal_one_bar_before_captures_jump(monkeypatch):
    n = 100
    close = np.full(n, 100.0)
    close[40:] = 110.0
    df = pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0},
                      index=pd.bdate_range("2025-01-01", periods=n))
    sig = pd.Series(0, index=df.index)
    sig.iloc[39] = 1
    monkeypatch.setattr(engine, "signal", lambda d, name: sig)
    r = run_backtest(df, "EMA 20/50 crossover", cost_pct=0.0, initial=100_000)
    assert r.equity.iloc[-1] == pytest.approx(110_000)


def test_costs_reduce_returns():
    df = demo_prices("COST", "5y")
    free = run_backtest(df, "EMA 20/50 crossover", cost_pct=0.0)
    paid = run_backtest(df, "EMA 20/50 crossover", cost_pct=0.01)
    assert free.metrics["trades"] > 0
    assert paid.metrics["total_return"] < free.metrics["total_return"]


def test_trades_table_sane():
    df = demo_prices("TRD", "5y")
    r = run_backtest(df, "EMA 20/50 crossover", cost_pct=0.0015)
    t = r.trades
    assert list(t.columns) == ["entry_date", "exit_date", "entry", "exit", "return", "open"]
    assert len(t) == r.metrics["trades"] > 0
    assert (t["exit_date"] >= t["entry_date"]).all()
    assert (t["entry"] > 0).all() and (t["exit"] > 0).all()
    assert np.isfinite(t["return"]).all()
    # fills happen at the close of the date shown
    for _, row in t.iterrows():
        assert df.loc[row["entry_date"], "Close"] == pytest.approx(row["entry"])
        assert df.loc[row["exit_date"], "Close"] == pytest.approx(row["exit"])
    # trades never overlap
    assert (t["entry_date"].iloc[1:].values >= t["exit_date"].iloc[:-1].values).all()


def test_zero_signal_means_flat_equity(monkeypatch):
    df = demo_prices("FLAT", "2y")
    monkeypatch.setattr(engine, "signal", lambda d, name: pd.Series(0, index=d.index))
    r = run_backtest(df, "SMA 50/200 crossover", initial=50_000)
    assert (r.equity == 50_000).all()
    assert r.metrics["trades"] == 0 and r.metrics["exposure"] == 0


def test_always_in_matches_buy_and_hold_minus_entry_cost(monkeypatch):
    df = demo_prices("ALL", "2y")
    monkeypatch.setattr(engine, "signal", lambda d, name: pd.Series(1, index=d.index))
    r = run_backtest(df, "SMA 50/200 crossover", cost_pct=0.0, initial=100_000)
    # in from the 2nd bar: equals buy-and-hold from bar 1
    expected = 100_000 * df["Close"].iloc[-1] / df["Close"].iloc[0]
    assert r.equity.iloc[-1] == pytest.approx(expected)
    assert r.trades["open"].iloc[-1]


def test_validation_and_warnings():
    with pytest.raises(ValueError):
        run_backtest(demo_prices("S", "1mo"), "SMA 50/200 crossover")
    with pytest.raises(ValueError):
        engine.signal(demo_prices("S", "1y"), "nope")
    r = run_backtest(demo_prices("W", "6mo"), "SMA 50/200 crossover")
    assert any("meaningful" in w for w in r.warnings)
    assert any("Past results" in w for w in r.warnings)


def test_rsi_reversion_state_machine():
    df = demo_prices("RSI", "5y")
    s = engine.signal(df, "RSI mean-reversion")
    assert set(s.unique()) <= {0, 1}
    assert s.dtype.kind in "iu"
