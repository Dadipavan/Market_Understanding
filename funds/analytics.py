"""Fund analytics, SIP maths and a rule-based fund score."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.base import Analysis, Reason
from scoring.technical import _na


def cagr(nav: pd.Series, years: float) -> float | None:
    end = nav.index[-1]
    start_t = end - pd.DateOffset(years=int(years)) if float(years).is_integer() else end - pd.Timedelta(days=int(365.25 * years))
    if nav.index[0] > start_t + pd.Timedelta(days=7):
        return None
    start_val = nav[nav.index <= start_t].iloc[-1]
    return float((nav.iloc[-1] / start_val) ** (1 / years) - 1)


def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1).min())


def rolling_returns(nav: pd.Series, years: int = 1) -> pd.Series:
    days = int(252 * years)
    return (nav / nav.shift(days) - 1).dropna()


def fund_metrics(nav: pd.Series, rf: float = 0.06) -> dict:
    nav = nav.dropna().sort_index()
    daily = nav.pct_change().dropna()
    vol = float(daily.std() * np.sqrt(252)) if len(daily) > 20 else None
    c1, c3, c5 = cagr(nav, 1), cagr(nav, 3), cagr(nav, 5)
    ref = c3 if c3 is not None else c1
    sharpe = ((ref - rf) / vol) if (ref is not None and vol) else None
    r1 = rolling_returns(nav, 1)
    return {
        "cagr_1y": c1, "cagr_3y": c3, "cagr_5y": c5, "volatility": vol, "max_drawdown": max_drawdown(nav),
        "sharpe": sharpe, "pct_positive_1y": float((r1 > 0).mean()) if len(r1) else None,
        "worst_1y": float(r1.min()) if len(r1) else None, "best_1y": float(r1.max()) if len(r1) else None,
        "history_years": (nav.index[-1] - nav.index[0]).days / 365.25,
    }


def fund_analysis(m: dict) -> tuple[Analysis, float]:
    R: list[Reason] = []
    c3 = m["cagr_3y"]
    R.append(_na("3-year return", 25, "Needs 3+ years of history.") if c3 is None else
             Reason("3-year return", c3 >= 0.12, f"3-year CAGR is {c3:.1%}. Compare with the category benchmark.", 25 if c3 >= 0.12 else 12 if c3 >= 0.08 else 0, 25))
    p = m["pct_positive_1y"]
    R.append(_na("Consistency", 20, "Needs 1+ year of history.") if p is None else
             Reason("Consistency", p >= 0.85, f"{p:.0%} of all 1-year windows were positive.", 20 if p >= 0.85 else 10 if p >= 0.70 else 0, 20))
    dd = m["max_drawdown"]
    R.append(Reason("Worst fall (max drawdown)", dd >= -0.25, f"Worst peak-to-trough fall was {dd:.0%}. This is the pain you must be able to sit through.", 15 if dd >= -0.25 else 7 if dd >= -0.40 else 0, 15))
    sh = m["sharpe"]
    R.append(_na("Risk-adjusted return (Sharpe)", 20, "Needs enough history.") if sh is None else
             Reason("Risk-adjusted return (Sharpe)", sh >= 0.5, f"Sharpe-style ratio is {sh:.2f}. Above ~0.5 means return is reasonable for the risk taken.", 20 if sh >= 0.5 else 10 if sh >= 0.25 else 0, 20))
    hy = m["history_years"]
    R.append(Reason("Track record length", hy >= 5, f"{hy:.1f} years of history. Longer means it has seen more market cycles.", 10 if hy >= 5 else 5 if hy >= 3 else 0, 10))
    c1 = m["cagr_1y"]
    R.append(_na("Recent year", 10, "Needs 1+ year of history.") if c1 is None else
             Reason("Recent year", c1 > 0, f"Last 1-year return is {c1:.1%}.", 10 if c1 > 0.08 else 5 if c1 > 0 else 0, 10))
    avail = [r for r in R if r.available]
    maxp = sum(r.max_points for r in avail)
    score = sum(r.points for r in avail) / maxp * 100 if maxp else 0
    cov = maxp / sum(r.max_points for r in R)
    verdict = "Strong" if score >= 70 else "Average" if score >= 45 else "Weak"
    risks = ["Scored on equity-style thresholds: compare debt/liquid funds only with their own category.",
             "Expense ratio, fund-manager changes and portfolio overlap are not in this free data: check them on the AMC factsheet."]
    return Analysis(round(score, 1), verdict, R, risks), round(cov, 2)


# ---------------------------------------------------------------- SIP maths
def sip_future_value(monthly: float, years: float, annual_return: float) -> dict:
    n = int(round(years * 12))
    r = (1 + annual_return) ** (1 / 12) - 1
    fv = monthly * (((1 + r) ** n - 1) / r) * (1 + r) if r else monthly * n
    invested = monthly * n
    return {"invested": invested, "future_value": fv, "gain": fv - invested}


def xirr(cashflows: list[tuple[pd.Timestamp, float]]) -> float | None:
    if not cashflows or not any(c < 0 for _, c in cashflows) or not any(c > 0 for _, c in cashflows):
        return None
    t0 = cashflows[0][0]
    yrs = np.array([(d - t0).days / 365.0 for d, _ in cashflows])
    amt = np.array([c for _, c in cashflows])

    def npv(r):
        return float(np.sum(amt / (1 + r) ** yrs))

    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def sip_backtest(nav: pd.Series, monthly: float, years: int) -> dict | None:
    nav = nav.dropna().sort_index()
    start = nav.index[-1] - pd.DateOffset(years=years)
    n = nav[nav.index >= start]
    if len(n) < 20:
        return None
    first_of_month = n.groupby([n.index.year, n.index.month]).head(1)
    units = (monthly / first_of_month).sum()
    invested = monthly * len(first_of_month)
    value = float(units * n.iloc[-1])
    cfs = [(d, -monthly) for d in first_of_month.index] + [(n.index[-1], value)]
    return {"invested": invested, "value": value, "gain": value - invested, "xirr": xirr(cfs), "installments": len(first_of_month)}


def expense_drag(monthly: float, years: float, gross_return: float, ter_low: float, ter_high: float) -> dict:
    a = sip_future_value(monthly, years, gross_return - ter_low)["future_value"]
    b = sip_future_value(monthly, years, gross_return - ter_high)["future_value"]
    return {"low_cost_value": a, "high_cost_value": b, "difference": a - b}
