"""Educational options maths: Black-Scholes, Greeks, strategy payoffs. No live option chain."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs_price(kind: str, S: float, K: float, T: float, r: float, sigma: float) -> float:
    """kind: 'call'|'put'. T in years, r and sigma as decimals."""
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "call":
        return S * _cdf(d1) - K * math.exp(-r * T) * _cdf(d2)
    return K * math.exp(-r * T) * _cdf(-d2) - S * _cdf(-d1)


def greeks(kind: str, S: float, K: float, T: float, r: float, sigma: float) -> dict:
    if T <= 0 or sigma <= 0:
        itm = (S > K) if kind == "call" else (S < K)
        return {"delta": (1.0 if kind == "call" else -1.0) if itm else 0.0, "gamma": 0.0, "theta_per_day": 0.0, "vega_per_1pct": 0.0, "rho_per_1pct": 0.0}
    sq = math.sqrt(T)
    d1 = (math.log(S / K) + (r + sigma ** 2 / 2) * T) / (sigma * sq)
    d2 = d1 - sigma * sq
    gamma = _pdf(d1) / (S * sigma * sq)
    vega = S * _pdf(d1) * sq / 100
    if kind == "call":
        delta = _cdf(d1)
        theta = (-S * _pdf(d1) * sigma / (2 * sq) - r * K * math.exp(-r * T) * _cdf(d2)) / 365
        rho = K * T * math.exp(-r * T) * _cdf(d2) / 100
    else:
        delta = _cdf(d1) - 1
        theta = (-S * _pdf(d1) * sigma / (2 * sq) + r * K * math.exp(-r * T) * _cdf(-d2)) / 365
        rho = -K * T * math.exp(-r * T) * _cdf(-d2) / 100
    return {"delta": delta, "gamma": gamma, "theta_per_day": theta, "vega_per_1pct": vega, "rho_per_1pct": rho}


def implied_vol(kind: str, price: float, S: float, K: float, T: float, r: float) -> float | None:
    lo, hi = 1e-4, 5.0
    intrinsic = max(S - K * math.exp(-r * T), 0) if kind == "call" else max(K * math.exp(-r * T) - S, 0)
    if T <= 0 or price < intrinsic - 1e-9 or price > bs_price(kind, S, K, T, r, hi):
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        if bs_price(kind, S, K, T, r, mid) > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


@dataclass
class Leg:
    kind: str       # 'call' | 'put' | 'stock'
    strike: float   # for stock: the entry price
    premium: float  # per unit (0 for stock)
    qty: int        # +long / -short (in units, i.e. lots * lot size)


def payoff(legs: list[Leg], prices: np.ndarray) -> np.ndarray:
    total = np.zeros_like(prices, dtype=float)
    for leg in legs:
        if leg.kind == "call":
            v = np.maximum(prices - leg.strike, 0) - leg.premium
        elif leg.kind == "put":
            v = np.maximum(leg.strike - prices, 0) - leg.premium
        else:
            v = prices - leg.strike
        total += v * leg.qty
    return total


def analyse_payoff(legs: list[Leg], spot: float, span: float = 0.4, points: int = 801) -> dict:
    prices = np.linspace(max(spot * (1 - span), 0.01), spot * (1 + span), points)
    pnl = payoff(legs, prices)
    slope_hi = pnl[-1] - pnl[-2]
    slope_lo = pnl[1] - pnl[0]
    be = []
    for i in range(1, len(pnl)):
        if pnl[i - 1] == 0:
            be.append(float(prices[i - 1]))
        elif pnl[i - 1] * pnl[i] < 0:
            x = prices[i - 1] + (prices[i] - prices[i - 1]) * (0 - pnl[i - 1]) / (pnl[i] - pnl[i - 1])
            be.append(float(x))
    be = sorted(set(round(b, 2) for b in be))
    max_profit = None if slope_hi > 1e-9 or slope_lo < -1e-9 else float(pnl.max())
    max_loss = None if slope_hi < -1e-9 or slope_lo > 1e-9 else float(pnl.min())
    return {"prices": prices, "pnl": pnl, "breakevens": be, "max_profit": max_profit, "max_loss": max_loss,
            "net_premium": float(sum(-l.premium * l.qty for l in legs if l.kind != "stock"))}


def preset(name: str, spot: float, step: float, premium_fn, units: int) -> list[Leg]:
    """Build a strategy around the at-the-money strike. premium_fn(kind, strike) -> premium."""
    atm = round(spot / step) * step
    c = lambda k: premium_fn("call", k)
    p = lambda k: premium_fn("put", k)
    if name == "Long call":
        return [Leg("call", atm, c(atm), units)]
    if name == "Long put":
        return [Leg("put", atm, p(atm), units)]
    if name == "Covered call":
        return [Leg("stock", spot, 0.0, units), Leg("call", atm + step, c(atm + step), -units)]
    if name == "Protective put":
        return [Leg("stock", spot, 0.0, units), Leg("put", atm - step, p(atm - step), units)]
    if name == "Bull call spread":
        return [Leg("call", atm, c(atm), units), Leg("call", atm + 2 * step, c(atm + 2 * step), -units)]
    if name == "Bear put spread":
        return [Leg("put", atm, p(atm), units), Leg("put", atm - 2 * step, p(atm - 2 * step), -units)]
    if name == "Long straddle":
        return [Leg("call", atm, c(atm), units), Leg("put", atm, p(atm), units)]
    if name == "Short straddle (UNLIMITED RISK)":
        return [Leg("call", atm, c(atm), -units), Leg("put", atm, p(atm), -units)]
    if name == "Iron condor":
        return [Leg("put", atm - 2 * step, p(atm - 2 * step), units), Leg("put", atm - step, p(atm - step), -units),
                Leg("call", atm + step, c(atm + step), -units), Leg("call", atm + 2 * step, c(atm + 2 * step), units)]
    raise ValueError(name)


PRESETS = ["Long call", "Long put", "Covered call", "Protective put", "Bull call spread", "Bear put spread",
           "Long straddle", "Short straddle (UNLIMITED RISK)", "Iron condor"]
