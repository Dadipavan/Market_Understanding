"""Approximate Indian equity trading costs and capital-gains tax.

Rates are approximate and change; always confirm with your broker's contract
note and a tax professional. Parameters are exposed so you can adjust them.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Rates:
    stt_delivery: float = 0.001          # 0.1% on buy and sell
    stt_intraday_sell: float = 0.00025   # 0.025% on sell only
    exchange_txn: float = 0.0000297      # NSE equity cash
    sebi: float = 0.000001               # Rs 10 per crore
    stamp_delivery_buy: float = 0.00015
    stamp_intraday_buy: float = 0.00003
    gst: float = 0.18                    # on brokerage + exchange + sebi
    dp_charge_sell: float = 15.34        # per scrip per sell day (delivery), approx
    brokerage_per_order: float = 0.0     # many brokers charge 0 for delivery; Rs 20 flat for intraday


RATES = Rates()


def trade_costs(price: float, qty: int, side: str, kind: str = "delivery", rates: Rates = RATES,
                brokerage: float | None = None) -> float:
    """Total charges for one order. side: 'buy'|'sell'. kind: 'delivery'|'intraday'."""
    turnover = price * qty
    b = rates.brokerage_per_order if brokerage is None else brokerage
    exch = turnover * rates.exchange_txn
    sebi = turnover * rates.sebi
    gst = (b + exch + sebi) * rates.gst
    if kind == "delivery":
        stt = turnover * rates.stt_delivery
        stamp = turnover * rates.stamp_delivery_buy if side == "buy" else 0.0
        dp = rates.dp_charge_sell if side == "sell" else 0.0
    else:
        stt = turnover * rates.stt_intraday_sell if side == "sell" else 0.0
        stamp = turnover * rates.stamp_intraday_buy if side == "buy" else 0.0
        dp = 0.0
    return round(b + exch + sebi + gst + stt + stamp + dp, 2)


def round_trip(buy: float, sell: float, qty: int, kind: str = "delivery", rates: Rates = RATES) -> dict:
    cb = trade_costs(buy, qty, "buy", kind, rates)
    cs = trade_costs(sell, qty, "sell", kind, rates)
    gross = (sell - buy) * qty
    return {"gross_pnl": round(gross, 2), "costs": round(cb + cs, 2), "net_pnl": round(gross - cb - cs, 2),
            "breakeven_move_pct": round((cb + cs) / (buy * qty) * 100, 3) if buy * qty else 0.0}


def capital_gains_tax(gain: float, holding_days: int, ltcg_exemption_left: float = 125_000.0) -> dict:
    """Listed equity (STT paid). STCG 20% if held <= 12 months. LTCG 12.5% above Rs 1.25 lakh/year.
    (Rates per Budget 2024; verify the current year's rules.) Losses are not modelled."""
    if gain <= 0:
        return {"type": "loss", "taxable": 0.0, "tax": 0.0, "rate": 0.0}
    if holding_days <= 365:
        return {"type": "STCG", "taxable": gain, "tax": round(gain * 0.20 * 1.04, 2), "rate": 0.20}
    taxable = max(0.0, gain - ltcg_exemption_left)
    return {"type": "LTCG", "taxable": taxable, "tax": round(taxable * 0.125 * 1.04, 2), "rate": 0.125}
