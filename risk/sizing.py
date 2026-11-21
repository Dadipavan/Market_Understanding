"""Risk-based position sizing."""
from __future__ import annotations

import math


def position_size(capital: float, risk_pct: float, entry: float, stop: float, max_position_pct: float = 100.0) -> dict:
    """Quantity such that hitting the stop loses at most risk_pct of capital.
    Capped so the position never exceeds max_position_pct of capital (no leverage)."""
    per_share_risk = entry - stop
    if capital <= 0 or entry <= 0 or per_share_risk <= 0:
        return {"qty": 0, "capital_used": 0.0, "risk_amount": 0.0, "per_share_risk": max(per_share_risk, 0.0),
                "note": "Stop must be below entry for a long trade."}
    risk_budget = capital * risk_pct / 100
    qty_by_risk = math.floor(risk_budget / per_share_risk)
    qty_by_cap = math.floor(capital * max_position_pct / 100 / entry)
    qty = max(0, min(qty_by_risk, qty_by_cap))
    note = "Limited by capital, not risk." if qty == qty_by_cap and qty_by_cap < qty_by_risk else ""
    if qty == 0:
        note = "Risk budget or capital too small for even one share at this stop distance."
    return {"qty": qty, "capital_used": round(qty * entry, 2), "risk_amount": round(qty * per_share_risk, 2),
            "per_share_risk": round(per_share_risk, 2), "note": note}
