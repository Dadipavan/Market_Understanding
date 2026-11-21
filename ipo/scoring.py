"""Rule-based IPO analysis. IPO data has no free reliable API, so the app works on a
table you maintain (CSV upload/edit) using numbers from the RHP/prospectus and NSE/BSE."""
from __future__ import annotations

import math

import pandas as pd

from core.base import Analysis, Reason
from scoring.technical import _na

COLUMNS = [
    "name", "exchange", "open_date", "close_date", "listing_date", "price_band_low", "price_band_high",
    "lot_size", "issue_size_cr", "fresh_issue_pct", "revenue_growth_pct", "profit_growth_pct", "roe_pct",
    "debt_to_equity", "issue_pe", "peer_pe", "promoter_holding_post_pct", "qib_x", "nii_x", "retail_x",
    "gmp_pct", "sample",
]
NUMERIC = [c for c in COLUMNS if c not in ("name", "exchange", "open_date", "close_date", "listing_date", "sample")]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for c in COLUMNS:
        if c not in d.columns:
            d[c] = pd.NA
    for c in NUMERIC:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    for c in ("open_date", "close_date", "listing_date"):
        d[c] = pd.to_datetime(d[c], errors="coerce")
    d["exchange"] = d["exchange"].fillna("Mainboard").astype(str)
    d["sample"] = d["sample"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes"])
    return d[COLUMNS].dropna(subset=["name"]).reset_index(drop=True)


def status(row: pd.Series, today: pd.Timestamp | None = None) -> str:
    t = (today or pd.Timestamp.now()).normalize()
    o, c, l = row["open_date"], row["close_date"], row["listing_date"]
    if pd.notna(l) and t >= l:
        return "Listed"
    if pd.notna(o) and t < o:
        return "Upcoming"
    if pd.notna(c) and t <= c:
        return "Open"
    return "Closed (awaiting listing)"


def _v(row, k):
    x = row.get(k)
    return None if x is None or (isinstance(x, float) and math.isnan(x)) or x is pd.NA else float(x)


def analyse_ipo(row: pd.Series) -> tuple[Analysis, float]:
    R: list[Reason] = []
    sme = str(row.get("exchange", "")).upper().startswith("SME")

    fresh = _v(row, "fresh_issue_pct")
    if fresh is None:
        R.append(_na("Fresh issue vs Offer for Sale", 15, "Fresh/OFS split not entered."))
    else:
        pts = 15 if fresh >= 60 else 8 if fresh >= 30 else 0
        R.append(Reason("Fresh issue vs Offer for Sale", pts == 15, f"{fresh:.0f}% is a fresh issue (money goes to the company); the rest is existing holders selling.", pts, 15))

    ipe, ppe = _v(row, "issue_pe"), _v(row, "peer_pe")
    if ipe is None or ppe is None or ppe <= 0:
        R.append(_na("Valuation vs listed peers", 20, "Issue P/E or peer P/E not entered."))
    elif ipe <= 0:
        R.append(Reason("Valuation vs listed peers", False, "Negative earnings: P/E not meaningful, so valuation rests on future promises.", 0, 20))
    else:
        ratio = ipe / ppe
        pts = 20 if ratio <= 0.9 else 10 if ratio <= 1.1 else 0
        R.append(Reason("Valuation vs listed peers", pts == 20, f"Issue P/E {ipe:.1f} vs peers {ppe:.1f} ({ratio:.0%} of peer level). Priced at a discount leaves room for listing and later gains.", pts, 20))

    pg = _v(row, "profit_growth_pct")
    R.append(_na("Profit growth", 10, "Profit growth not entered.") if pg is None else
             Reason("Profit growth", pg >= 15, f"Profit grew {pg:.0f}% in the latest year.", 10 if pg >= 15 else 5 if pg > 0 else 0, 10))
    rg = _v(row, "revenue_growth_pct")
    R.append(_na("Revenue growth", 10, "Revenue growth not entered.") if rg is None else
             Reason("Revenue growth", rg >= 15, f"Revenue grew {rg:.0f}% in the latest year.", 10 if rg >= 15 else 5 if rg > 0 else 0, 10))
    roe = _v(row, "roe_pct")
    R.append(_na("Return on equity", 10, "ROE not entered.") if roe is None else
             Reason("Return on equity", roe >= 15, f"ROE is {roe:.0f}%.", 10 if roe >= 15 else 5 if roe >= 10 else 0, 10))
    de = _v(row, "debt_to_equity")
    R.append(_na("Debt / equity", 10, "Debt/equity not entered.") if de is None else
             Reason("Debt / equity", de <= 1, f"Debt/equity is {de:.2f}.", 10 if de <= 0.5 else 6 if de <= 1 else 0, 10))
    ph = _v(row, "promoter_holding_post_pct")
    R.append(_na("Promoter holding after IPO", 5, "Not entered.") if ph is None else
             Reason("Promoter holding after IPO", ph >= 50, f"Promoters keep {ph:.0f}% after the issue. Higher means more skin in the game.", 5 if ph >= 50 else 2 if ph >= 35 else 0, 5))
    profitable = (pg is not None and roe is not None and roe > 0)
    R.append(_na("Profitable business", 5, "Needs ROE.") if roe is None else
             Reason("Profitable business", roe > 0, "The company is profitable." if roe > 0 else "Loss-making: you are betting on a future turnaround.", 5 if roe > 0 else 0, 5))
    qib = _v(row, "qib_x")
    R.append(_na("Institutional demand (QIB)", 10, "Subscription data appears only after the issue opens.") if qib is None else
             Reason("Institutional demand (QIB)", qib >= 10, f"QIB portion subscribed {qib:.1f}x. Institutions do deeper research than most retail applicants.", 10 if qib >= 10 else 5 if qib >= 3 else 0, 10))
    gmp = _v(row, "gmp_pct")
    R.append(_na("Grey-market sentiment (GMP)", 5, "GMP not entered.") if gmp is None else
             Reason("Grey-market sentiment (GMP)", gmp >= 10, f"GMP is {gmp:.0f}% of the upper band. Unofficial and easily manipulated: low weight.", 5 if gmp >= 10 else 2 if gmp > 0 else 0, 5))

    avail = [r for r in R if r.available]
    maxp = sum(r.max_points for r in avail)
    cov = maxp / sum(r.max_points for r in R)
    score = sum(r.points for r in avail) / maxp * 100 if maxp else 0.0

    risks = []
    if sme:
        risks.append("SME IPO: thin trading, wide spreads, bigger lots and higher manipulation risk. Treat as high-risk.")
    if fresh is not None and fresh < 30:
        risks.append("Mostly an Offer for Sale: existing investors are cashing out.")
    if roe is not None and roe <= 0:
        risks.append("Loss-making company.")
    if cov < 0.6:
        risks.append(f"Only {cov:.0%} of the rules had data. Fill in more fields from the RHP before deciding.")

    if cov < 0.5:
        verdict = "Insufficient data"
    elif score >= 70:
        verdict = "Apply"
    elif score >= 50:
        verdict = "Apply with caution"
    else:
        verdict = "Avoid"
    if sme and verdict == "Apply":
        verdict = "Apply with caution"
    return Analysis(round(score, 1), verdict, R, risks), round(cov, 2)


def application_amount(row: pd.Series, lots: int = 1) -> float | None:
    hi, lot = _v(row, "price_band_high"), _v(row, "lot_size")
    return None if hi is None or lot is None else hi * lot * lots


def estimated_listing_price(row: pd.Series) -> float | None:
    hi, gmp = _v(row, "price_band_high"), _v(row, "gmp_pct")
    return None if hi is None or gmp is None else hi * (1 + gmp / 100)
