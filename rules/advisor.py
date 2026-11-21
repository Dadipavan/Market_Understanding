"""The advisor: combines technical + fundamental rule scores into an explained report,
and builds risk-managed trade setups. Fully deterministic and explainable (no AI)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from core.base import Analysis, Reason
from indicators.technical import support_resistance
from risk.costs import round_trip
from risk.sizing import position_size
from scoring.fundamental import fundamental_analysis
from scoring.technical import technical_analysis

DISCLAIMER = "Educational analysis from fixed rules, not investment advice. Verify prices and numbers on NSE/your broker before acting."


@dataclass
class InvestingReport:
    symbol: str
    verdict: str
    level: str                      # success | info | warning | error  (UI colour)
    score: float
    technical: Analysis
    fundamental: Analysis | None
    tech_coverage: float
    fund_coverage: float
    summary: str
    entry_zone: tuple[float, float] | None
    invalidation: float | None
    risks: list[str] = field(default_factory=list)
    indicators: pd.DataFrame | None = None
    verified: bool = True
    as_of: str = ""


def _top(reasons: list[Reason], passed: bool, k: int = 3) -> list[str]:
    rs = [r for r in reasons if r.available and r.passed == passed]
    rs.sort(key=lambda r: r.max_points, reverse=True)
    return [r.rule.lower() for r in rs[:k]]


def investing_report(symbol: str, df: pd.DataFrame, info: dict | None, verified: bool = True) -> InvestingReport:
    tech, ind, tcov = technical_analysis(df)
    fund, fcov = fundamental_analysis(info)
    have_fund = fund.verdict != "Fundamentals unavailable" and fcov >= 0.4

    if have_fund:
        score = 0.6 * fund.score + 0.4 * tech.score
    else:
        score = tech.score

    if score >= 75:
        verdict, level = "Strong candidate: accumulate", "success"
    elif score >= 60:
        verdict, level = "Good: buy in tranches / on dips", "success"
    elif score >= 45:
        verdict, level = "Watchlist: wait for a better price or confirmation", "warning"
    else:
        verdict, level = "Avoid for now", "error"

    caveats = []
    if not have_fund:
        caveats.append("Fundamentals missing or too sparse, so this is a price-trend view only.")
        if verdict.startswith(("Strong", "Good")):
            verdict, level = "Watchlist: price trend is positive but business quality is unverified", "warning"
    if not verified:
        caveats.append("Data failed one or more quality checks: verify prices on NSE before relying on this.")
        verdict = "UNVERIFIED DATA - " + verdict
        level = "warning" if level == "success" else level

    parts = []
    good = _top(fund.reasons, True) if have_fund else []
    bad = _top(fund.reasons, False) if have_fund else []
    tgood, tbad = _top(tech.reasons, True, 2), _top(tech.reasons, False, 2)
    if good:
        parts.append("Strengths: " + ", ".join(good) + ".")
    if bad:
        parts.append("Weak spots: " + ", ".join(bad) + ".")
    if tgood:
        parts.append("Price action supportive on: " + ", ".join(tgood) + ".")
    if tbad:
        parts.append("Price action not yet supportive on: " + ", ".join(tbad) + ".")
    summary = " ".join(parts) or "Not enough data to summarise."

    entry_zone = invalidation = None
    if not ind.empty:
        close = float(ind["Close"].iloc[-1])
        sup, _ = support_resistance(df)
        e50 = ind["EMA50"].dropna()
        e200 = ind["EMA200"].dropna()
        atr = float(ind["ATR"].dropna().iloc[-1]) if not ind["ATR"].dropna().empty else close * 0.02
        hi = min(close, float(e50.iloc[-1])) if not e50.empty else close
        lo_candidates = [x for x in (sup, float(e200.iloc[-1]) if not e200.empty else None) if x is not None and x < hi]
        lo = max(lo_candidates) if lo_candidates else hi * 0.95
        entry_zone = (round(min(lo, hi), 2), round(hi, 2))
        floor = min([x for x in (sup, float(e200.iloc[-1]) if not e200.empty else None) if x is not None] or [close * 0.9])
        invalidation = round(floor - atr, 2)

    risks = list(dict.fromkeys(tech.risks + (fund.risks if have_fund else []) + caveats))
    return InvestingReport(symbol, verdict, level, round(score, 1), tech, fund if have_fund else None,
                           tcov, fcov, summary, entry_zone, invalidation, risks, ind, verified, tech.data_as_of)


# ---------------------------------------------------------------- trading
@dataclass
class TradeSetup:
    symbol: str
    grade: str                  # A | B | No trade
    level: str
    score: float
    entry: float
    stop: float
    target1: float
    target2: float
    risk_reward_t1: float
    nearest_resistance: float | None
    sizing: dict
    costs_t1: dict | None
    notes: list[str]
    technical: Analysis


def trading_setup(symbol: str, df: pd.DataFrame, capital: float, risk_pct: float = 1.0,
                  kind: str = "delivery", max_position_pct: float = 100.0) -> TradeSetup | None:
    tech, ind, _ = technical_analysis(df)
    if ind.empty:
        return None
    close = float(ind["Close"].iloc[-1])
    atr_s = ind["ATR"].dropna()
    atr = float(atr_s.iloc[-1]) if not atr_s.empty else close * 0.02
    sup, res = support_resistance(df)

    stop = close - 2 * atr
    if sup is not None and sup < close and (close - sup) < 3 * atr:
        stop = max(stop, sup - 0.5 * atr)  # tighter, structure-based stop
    stop = min(stop, close - max(close * 0.015, atr))  # at least 1.5% or 1 ATR below entry: avoids absurdly tight stops/huge sizes
    risk = close - stop
    t1, t2 = close + 2 * risk, close + 3 * risk
    sizing = position_size(capital, risk_pct, close, stop, max_position_pct)

    notes = []
    if res is not None and res < t1:
        rr_res = (res - close) / risk if risk > 0 else 0
        notes.append(f"Resistance near {res:,.2f} gives only {rr_res:.1f}R before a likely stall. Consider waiting for a breakout above it.")
    if tech.score >= 70:
        grade, level = "A", "success"
    elif tech.score >= 55:
        grade, level = "B", "info"
        notes.append("B-grade: some rules are not aligned. Use half size or wait for confirmation.")
    else:
        grade, level = "No trade", "error"
        notes.append("Not enough rules agree. Preserving capital is a valid decision.")
    if sizing["qty"] == 0:
        notes.append(sizing.get("note", ""))
    ct = round_trip(close, t1, sizing["qty"], kind) if sizing["qty"] > 0 else None
    if ct and ct["breakeven_move_pct"] > 0.3:
        notes.append(f"Costs need a {ct['breakeven_move_pct']:.2f}% move just to break even.")
    return TradeSetup(symbol, grade, level, tech.score, round(close, 2), round(stop, 2), round(t1, 2), round(t2, 2),
                      round((t1 - close) / risk, 2) if risk > 0 else 0.0, res, sizing, ct, [n for n in notes if n], tech)
