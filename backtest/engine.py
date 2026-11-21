"""Simple, honest long-only backtester with costs, benchmarked against buy-and-hold."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from indicators.technical import ema, macd, rsi, sma

STRATEGIES = {
    "SMA 50/200 crossover": "Hold while the 50-day average is above the 200-day (classic trend following).",
    "EMA 20/50 crossover": "Faster trend following: hold while the 20-day EMA is above the 50-day EMA.",
    "Trend + momentum": "Hold while price > 200-day EMA, RSI between 50 and 75, and MACD above signal.",
    "RSI mean-reversion": "Buy when RSI < 30 (oversold), sell when RSI > 55. Works best in sideways markets.",
}


def signal(df: pd.DataFrame, name: str) -> pd.Series:
    c = df["Close"]
    if name == "SMA 50/200 crossover":
        s = (sma(c, 50) > sma(c, 200))
    elif name == "EMA 20/50 crossover":
        s = (ema(c, 20) > ema(c, 50))
    elif name == "Trend + momentum":
        m = macd(c)
        r = rsi(c)
        s = (c > ema(c, 200)) & (r.between(50, 75)) & (m["MACD"] > m["MACD_signal"])
    elif name == "RSI mean-reversion":
        r = rsi(c)
        pos, out = 0, []
        for v in r:
            if pos == 0 and v == v and v < 30:
                pos = 1
            elif pos == 1 and v == v and v > 55:
                pos = 0
            out.append(pos)
        s = pd.Series(out, index=c.index).astype(bool)
    else:
        raise ValueError(f"Unknown strategy: {name}")
    return s.fillna(False).astype(int)


@dataclass
class BacktestResult:
    equity: pd.Series
    benchmark: pd.Series
    metrics: dict
    trades: pd.DataFrame
    warnings: list[str]


def _max_dd(eq: pd.Series) -> float:
    return float((eq / eq.cummax() - 1).min()) if len(eq) else 0.0


def _stats(eq: pd.Series, rets: pd.Series, rf: float) -> dict:
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    total = float(eq.iloc[-1] / eq.iloc[0] - 1)
    cagr = float((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1) if eq.iloc[-1] > 0 else -1.0
    sd = float(rets.std())
    sharpe = float((rets.mean() - rf / 252) / sd * np.sqrt(252)) if sd > 0 else 0.0
    return {"total_return": total, "cagr": cagr, "max_drawdown": _max_dd(eq), "sharpe": sharpe}


def run_backtest(df: pd.DataFrame, strategy: str, cost_pct: float = 0.0015, initial: float = 100_000.0,
                 rf: float = 0.06) -> BacktestResult:
    warnings: list[str] = []
    if len(df) < 60:
        raise ValueError("Need at least 60 bars to backtest.")
    if strategy.startswith("SMA 50/200") and len(df) < 260:
        warnings.append("Less than ~1 year of data after the 200-day warm-up: results are not meaningful.")
    c = df["Close"]
    ret = c.pct_change().fillna(0.0)
    sig = signal(df, strategy)
    pos = sig.shift(1).fillna(0)                      # act on the NEXT bar: no look-ahead
    turnover = pos.diff().abs().fillna(pos.abs())
    strat = pos * ret - turnover * cost_pct
    equity = initial * (1 + strat).cumprod()
    bench = initial * (1 + ret).cumprod()

    # trades
    trades, entry_i = [], None
    pv = pos.values
    for i in range(len(pv)):
        if pv[i] == 1 and entry_i is None:
            entry_i = i
        if (pv[i] == 0 or i == len(pv) - 1) and entry_i is not None:
            exit_i = i
            # position at bar i earns close[i-1]->close[i], so entry fills at close[entry-1]
            # and an exit signalled on bar i-1 fills at close[i-1].
            ep = float(c.iloc[entry_i - 1]) if entry_i > 0 else float(c.iloc[entry_i])
            xp = float(c.iloc[i - 1]) if pv[i] == 0 else float(c.iloc[i])
            trades.append({"entry_date": c.index[max(entry_i - 1, 0)], "exit_date": c.index[i - 1] if pv[i] == 0 else c.index[i], "entry": ep, "exit": xp,
                           "return": xp / ep - 1 - 2 * cost_pct, "open": bool(pv[i] == 1)})
            entry_i = None
    tdf = pd.DataFrame(trades, columns=["entry_date", "exit_date", "entry", "exit", "return", "open"])

    m = _stats(equity, strat, rf)
    b = _stats(bench, ret, rf)
    m.update({
        "bh_total_return": b["total_return"], "bh_cagr": b["cagr"], "bh_max_drawdown": b["max_drawdown"], "bh_sharpe": b["sharpe"],
        "trades": int(len(tdf)),
        "win_rate": float((tdf["return"] > 0).mean()) if len(tdf) else 0.0,
        "avg_trade": float(tdf["return"].mean()) if len(tdf) else 0.0,
        "exposure": float(pos.mean()),
    })
    if len(tdf) < 10:
        warnings.append(f"Only {len(tdf)} trades: too few to trust statistically.")
    if m["total_return"] < m["bh_total_return"]:
        warnings.append("This strategy did not beat simply buying and holding over this period.")
    warnings.append("Past results do not predict future returns. Rules tuned on one stock/period often fail elsewhere (overfitting).")
    return BacktestResult(equity, bench, m, tdf, warnings)
