"""Bond and fixed-income calculators."""
from __future__ import annotations


def cashflows(face: float, coupon_rate: float, years: float, freq: int = 2) -> list[tuple[float, float]]:
    n = int(round(years * freq))
    c = face * coupon_rate / freq
    return [((i + 1) / freq, c + (face if i == n - 1 else 0.0)) for i in range(n)]


def price_from_ytm(face: float, coupon_rate: float, years: float, ytm: float, freq: int = 2) -> float:
    return sum(cf / (1 + ytm / freq) ** (t * freq) for t, cf in cashflows(face, coupon_rate, years, freq))


def ytm_from_price(price: float, face: float, coupon_rate: float, years: float, freq: int = 2) -> float | None:
    lo, hi = -0.5, 2.0
    if price_from_ytm(face, coupon_rate, years, lo, freq) < price or price_from_ytm(face, coupon_rate, years, hi, freq) > price:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if price_from_ytm(face, coupon_rate, years, mid, freq) > price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def duration(face: float, coupon_rate: float, years: float, ytm: float, freq: int = 2) -> dict:
    cfs = cashflows(face, coupon_rate, years, freq)
    pv = [cf / (1 + ytm / freq) ** (t * freq) for t, cf in cfs]
    price = sum(pv)
    mac = sum(t * p for (t, _), p in zip(cfs, pv)) / price
    mod = mac / (1 + ytm / freq)
    return {"price": price, "macaulay": mac, "modified": mod, "price_change_per_1pct": -mod * price * 0.01}


def after_tax_yield(pre_tax_yield: float, tax_rate: float) -> float:
    return pre_tax_yield * (1 - tax_rate)


def current_yield(price: float, face: float, coupon_rate: float) -> float:
    return face * coupon_rate / price if price else 0.0
