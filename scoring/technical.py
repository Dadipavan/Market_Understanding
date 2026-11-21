"""Rule-based technical score (0-100). Every rule reports points and a plain-language reason."""
from __future__ import annotations

import pandas as pd

from core.base import Analysis, Reason
from indicators.technical import add_indicators


def _last(s: pd.Series):
    s = s.dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _na(rule: str, max_points: float, why: str) -> Reason:
    return Reason(rule, False, why, 0.0, max_points, available=False)


def finish(reasons: list[Reason], bands: tuple[float, float] = (70, 40), labels=("Bullish", "Neutral", "Bearish")) -> tuple[float, float, str]:
    avail = [r for r in reasons if r.available]
    maxp = sum(r.max_points for r in avail)
    total_max = sum(r.max_points for r in reasons) or 1
    score = (sum(r.points for r in avail) / maxp * 100) if maxp else 0.0
    coverage = maxp / total_max
    hi, lo = bands
    verdict = labels[0] if score >= hi else labels[1] if score >= lo else labels[2]
    return round(score, 1), round(coverage, 2), verdict


def technical_analysis(df: pd.DataFrame) -> tuple[Analysis, pd.DataFrame, float]:
    """Returns (analysis, indicator frame, coverage 0-1)."""
    if df is None or len(df) < 30:
        return Analysis(0, "Not enough data", [], ["Fewer than 30 price bars: technical analysis not possible."]), pd.DataFrame(), 0.0
    d = add_indicators(df)
    close = float(d["Close"].iloc[-1])
    R: list[Reason] = []

    e200, e50 = _last(d["EMA200"]), _last(d["EMA50"])
    if e200 is None:
        R.append(_na("Long-term trend", 20, "Needs 200+ bars of history for the 200-day average."))
        R.append(_na("Medium vs long trend", 15, "Needs 200+ bars of history."))
    else:
        ok = close > e200
        R.append(Reason("Long-term trend", ok, f"Price {close:,.2f} is {'above' if ok else 'below'} the 200-day average {e200:,.2f}.", 20 if ok else 0, 20))
        ok = e50 is not None and e50 > e200
        R.append(Reason("Medium vs long trend", ok, f"50-day average is {'above' if ok else 'below'} the 200-day average (golden/death-cross zone).", 15 if ok else 0, 15))

    if e50 is None:
        R.append(_na("Price vs 50-day average", 10, "Needs 50+ bars."))
    else:
        ok = close > e50
        R.append(Reason("Price vs 50-day average", ok, f"Price is {'above' if ok else 'below'} the 50-day average {e50:,.2f}.", 10 if ok else 0, 10))

    r = _last(d["RSI"])
    if r is None:
        R.append(_na("Momentum (RSI)", 15, "Needs 15+ bars."))
    else:
        if 50 <= r <= 70:
            pts, txt = 15, "healthy bullish momentum (50-70)"
        elif 40 <= r < 50 or 70 < r <= 80:
            pts, txt = 7, "borderline: " + ("weak momentum" if r < 50 else "getting overbought")
        else:
            pts, txt = 0, "oversold (<40)" if r < 40 else "very overbought (>80)"
        R.append(Reason("Momentum (RSI)", pts >= 15, f"RSI is {r:.0f}: {txt}.", pts, 15))

    m, ms = _last(d["MACD"]), _last(d["MACD_signal"])
    if m is None or ms is None:
        R.append(_na("MACD trend", 10, "Needs 35+ bars."))
        R.append(_na("MACD acceleration", 5, "Needs 35+ bars."))
    else:
        ok = m > ms
        R.append(Reason("MACD trend", ok, f"MACD is {'above' if ok else 'below'} its signal line.", 10 if ok else 0, 10))
        h = d["MACD_hist"].dropna()
        rising = len(h) >= 3 and h.iloc[-1] > h.iloc[-3]
        R.append(Reason("MACD acceleration", rising, f"MACD histogram is {'rising' if rising else 'not rising'} over 3 bars.", 5 if rising else 0, 5))

    v5, v20 = _last(d["VolAvg5"]), _last(d["VolAvg20"])
    if v5 is None or v20 is None or v20 == 0:
        R.append(_na("Volume confirmation", 5, "Needs 20+ bars with volume."))
    else:
        ok = v5 > v20
        R.append(Reason("Volume confirmation", ok, f"Recent volume is {'above' if ok else 'below'} the 20-day average ({v5 / v20:.0%} of it).", 5 if ok else 0, 5))

    bb_up = _last(d["BB_up"])
    if e50 is None or bb_up is None:
        R.append(_na("Not overstretched", 10, "Needs 50+ bars."))
    else:
        stretch = close / e50 - 1
        ok = stretch <= 0.15 and close <= bb_up
        R.append(Reason("Not overstretched", ok, f"Price is {stretch:+.1%} from the 50-day average{' and above the upper Bollinger band' if close > bb_up else ''}. Far above average often means a pullback risk.", 10 if ok else 0, 10))

    a = _last(d["ATR"])
    if a is None:
        R.append(_na("Volatility", 10, "Needs 15+ bars."))
    else:
        apct = a / close
        ok = apct < 0.04
        R.append(Reason("Volatility", ok, f"Typical daily range (ATR) is {apct:.1%} of price. Under 4% is easier to manage.", 10 if ok else 0, 10))

    score, coverage, verdict = finish(R)
    risks = []
    if r is not None and r > 75:
        risks.append("Overbought: a short-term pullback is common.")
    if a is not None and a / close >= 0.04:
        risks.append("High volatility: wider stops and smaller position sizes are needed.")
    if coverage < 0.7:
        risks.append(f"Only {coverage:.0%} of technical rules could be evaluated (short history).")
    return Analysis(score, verdict, R, risks, data_as_of=f"{df.index[-1]:%Y-%m-%d}"), d, coverage
