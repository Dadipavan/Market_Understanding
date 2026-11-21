"""Rule-based fundamental score: quality, growth, balance sheet, valuation, ownership."""
from __future__ import annotations

from core.base import Analysis, Reason
from scoring.technical import _na, finish

FINANCIAL_SECTORS = {"Financial Services", "Financials", "Banks", "Insurance"}


def fundamental_analysis(info: dict | None) -> tuple[Analysis, float]:
    if not info:
        return Analysis(0, "Fundamentals unavailable", [], ["No fundamentals could be loaded. Check Screener.in manually."]), 0.0
    sector = info.get("sector")
    is_fin = sector in FINANCIAL_SECTORS
    R: list[Reason] = []

    def get(k):
        return info.get(k)

    roe = get("roe")
    if roe is None:
        R.append(_na("Return on equity", 15, "ROE not available."))
    else:
        pts = 15 if roe >= 0.15 else 8 if roe >= 0.10 else 0
        R.append(Reason("Return on equity", pts == 15, f"ROE is {roe:.1%}. 15%+ suggests the business earns good returns on shareholders' money.", pts, 15))

    pm = get("profit_margin")
    if pm is None:
        R.append(_na("Net profit margin", 10, "Profit margin not available."))
    else:
        pts = 10 if pm >= 0.10 else 5 if pm >= 0.05 else 0
        R.append(Reason("Net profit margin", pts == 10, f"Net margin is {pm:.1%}.", pts, 10))

    om = get("operating_margin")
    if om is None:
        R.append(_na("Operating margin", 5, "Operating margin not available."))
    else:
        R.append(Reason("Operating margin", om >= 0.15, f"Operating margin is {om:.1%}.", 5 if om >= 0.15 else 0, 5))

    rg = get("revenue_growth")
    if rg is None:
        R.append(_na("Revenue growth", 10, "Revenue growth not available."))
    else:
        pts = 10 if rg >= 0.10 else 5 if rg >= 0.05 else 0
        R.append(Reason("Revenue growth", pts == 10, f"Latest revenue growth is {rg:.1%}.", pts, 10))

    eg = get("earnings_growth")
    if eg is None:
        R.append(_na("Earnings growth", 10, "Earnings growth not available."))
    else:
        pts = 10 if eg >= 0.10 else 5 if eg > 0 else 0
        R.append(Reason("Earnings growth", pts == 10, f"Latest earnings growth is {eg:.1%}.", pts, 10))

    dte = get("debt_to_equity")
    if is_fin:
        R.append(_na("Debt / equity", 10, "Not meaningful for banks and lenders (debt is their raw material)."))
    elif dte is None:
        R.append(_na("Debt / equity", 10, "Debt/equity not available."))
    else:
        pts = 10 if dte <= 0.5 else 6 if dte <= 1 else 0
        R.append(Reason("Debt / equity", dte <= 1, f"Debt/equity is {dte:.2f}. Under 1 is generally comfortable.", pts, 10))

    cr = get("current_ratio")
    if is_fin or cr is None:
        R.append(_na("Short-term liquidity", 5, "Not applicable or not available."))
    else:
        R.append(Reason("Short-term liquidity", cr >= 1.2, f"Current ratio is {cr:.2f}. Above ~1.2 means short-term bills are covered.", 5 if cr >= 1.2 else 0, 5))

    pe = get("pe")
    if pe is None:
        R.append(_na("Valuation (P/E)", 15, "P/E not available (often means the company is loss-making)."))
    elif pe <= 0:
        R.append(Reason("Valuation (P/E)", False, "Negative earnings: P/E is not meaningful.", 0, 15))
    else:
        pts = 15 if pe <= 20 else 8 if pe <= 35 else 0
        R.append(Reason("Valuation (P/E)", pts == 15, f"P/E is {pe:.1f}. Compare with the sector: below 20 is cheaper, above 35 is expensive unless growth is high.", pts, 15))

    if pe is not None and pe > 0 and eg is not None and eg > 0:
        peg = pe / (eg * 100)
        pts = 10 if peg <= 1.5 else 5 if peg <= 2.5 else 0
        R.append(Reason("Growth-adjusted valuation (PEG)", pts == 10, f"PEG is {peg:.2f}. Under 1.5 means you pay a reasonable price for the growth.", pts, 10))
    else:
        R.append(_na("Growth-adjusted valuation (PEG)", 10, "Needs positive P/E and earnings growth."))

    ph = get("promoter_holding")
    if ph is None:
        R.append(_na("Insider / promoter holding", 10, "Holding data not available. Check pledging on NSE/BSE."))
    else:
        pts = 10 if 0.35 <= ph <= 0.75 else 5 if ph >= 0.20 else 0
        R.append(Reason("Insider / promoter holding", pts == 10, f"Insiders hold {ph:.1%}. Meaningful ownership aligns interests; check pledged shares separately.", pts, 10))

    score, coverage, verdict = finish(R, bands=(70, 45), labels=("Strong", "Average", "Weak"))
    risks = []
    pe_v = get("pe")
    if pe_v is not None and pe_v > 50:
        risks.append(f"Very high P/E ({pe_v:.0f}): expectations are already high.")
    if pe_v is None or (pe_v is not None and pe_v <= 0):
        risks.append("Company may be loss-making: valuation rules are limited.")
    if not is_fin and dte is not None and dte > 1.5:
        risks.append(f"High debt (D/E {dte:.1f}): sensitive to interest rates and slowdowns.")
    if coverage < 0.7:
        risks.append(f"Only {coverage:.0%} of fundamental rules had data. Treat the score with caution and verify on Screener.in.")
    return Analysis(score, verdict, R, risks, source=info.get("source", "")), coverage
