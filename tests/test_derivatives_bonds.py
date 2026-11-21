import math

import numpy as np
import pytest

from bonds import calc
from derivatives.options import Leg, PRESETS, analyse_payoff, bs_price, greeks, implied_vol, payoff, preset


# ------------------------------------------------------------ options
def test_black_scholes_known_value():
    assert bs_price("call", 100, 100, 1, 0.05, 0.20) == pytest.approx(10.4506, abs=1e-3)
    assert bs_price("put", 100, 100, 1, 0.05, 0.20) == pytest.approx(5.5735, abs=1e-3)


def test_put_call_parity():
    for S, K, T, r, sg in [(100, 90, 0.5, 0.06, 0.3), (250, 260, 1.0, 0.07, 0.25), (50, 50, 0.1, 0.05, 0.4)]:
        c, p = bs_price("call", S, K, T, r, sg), bs_price("put", S, K, T, r, sg)
        assert c - p == pytest.approx(S - K * math.exp(-r * T), abs=1e-9)


def test_expired_option_is_intrinsic():
    assert bs_price("call", 110, 100, 0, 0.05, 0.2) == 10 and bs_price("put", 110, 100, 0, 0.05, 0.2) == 0


def test_greeks_sanity():
    gc = greeks("call", 100, 100, 1, 0.05, 0.20)
    gp = greeks("put", 100, 100, 1, 0.05, 0.20)
    assert gc["delta"] == pytest.approx(0.6368, abs=1e-3)
    assert gp["delta"] == pytest.approx(gc["delta"] - 1)
    assert gc["gamma"] == pytest.approx(gp["gamma"]) and gc["gamma"] > 0
    assert gc["vega_per_1pct"] == pytest.approx(gp["vega_per_1pct"]) and gc["vega_per_1pct"] > 0
    assert gc["theta_per_day"] < 0 and gp["theta_per_day"] < 0
    assert gc["rho_per_1pct"] > 0 > gp["rho_per_1pct"]
    # finite-difference check of delta
    h = 0.01
    fd = (bs_price("call", 100 + h, 100, 1, 0.05, 0.2) - bs_price("call", 100 - h, 100, 1, 0.05, 0.2)) / (2 * h)
    assert gc["delta"] == pytest.approx(fd, abs=1e-4)


def test_implied_vol_round_trip():
    for kind in ("call", "put"):
        px = bs_price(kind, 100, 105, 0.5, 0.06, 0.27)
        assert implied_vol(kind, px, 100, 105, 0.5, 0.06) == pytest.approx(0.27, abs=1e-4)
    assert implied_vol("call", 0.01, 150, 100, 1, 0.05) is None   # below intrinsic
    assert implied_vol("call", 10, 100, 100, 0, 0.05) is None


def test_long_call_payoff():
    a = analyse_payoff([Leg("call", 100, 5, 1)], 100)
    assert a["breakevens"] == [pytest.approx(105, abs=0.1)]
    assert a["max_loss"] == pytest.approx(-5) and a["max_profit"] is None
    assert a["net_premium"] == -5


def test_straddle_payoffs():
    long_s = analyse_payoff([Leg("call", 100, 5, 1), Leg("put", 100, 5, 1)], 100)
    assert long_s["breakevens"] == [pytest.approx(90, abs=0.1), pytest.approx(110, abs=0.1)]
    assert long_s["max_loss"] == pytest.approx(-10) and long_s["max_profit"] is None
    short_s = analyse_payoff([Leg("call", 100, 5, -1), Leg("put", 100, 5, -1)], 100)
    assert short_s["max_profit"] == pytest.approx(10) and short_s["max_loss"] is None   # UNLIMITED risk detected


def test_defined_risk_strategies_are_bounded():
    prem = lambda kind, k: bs_price(kind, 100, k, 30 / 365, 0.07, 0.2)
    for name in ("Bull call spread", "Bear put spread", "Iron condor"):
        legs = preset(name, 100, 5, prem, 50)
        a = analyse_payoff(legs, 100)
        assert a["max_loss"] is not None and a["max_profit"] is not None, name
        assert a["max_loss"] < 0 < a["max_profit"], name
    assert len(preset("Iron condor", 100, 5, prem, 50)) == 4


def test_all_presets_build_and_payoff_vector():
    prem = lambda kind, k: bs_price(kind, 100, k, 30 / 365, 0.07, 0.2)
    for name in PRESETS:
        legs = preset(name, 100, 5, prem, 25)
        p = payoff(legs, np.linspace(50, 150, 11))
        assert p.shape == (11,) and np.isfinite(p).all()
    with pytest.raises(ValueError):
        preset("nope", 100, 5, prem, 1)


def test_covered_call_shape():
    a = analyse_payoff([Leg("stock", 100, 0, 1), Leg("call", 105, 2, -1)], 100)
    assert a["max_profit"] == pytest.approx(7)          # (105-100) + 2
    assert a["max_loss"] is None                        # downside is open (stock can fall)
    assert a["breakevens"] == [pytest.approx(98, abs=0.1)]


# ------------------------------------------------------------ bonds
def test_par_bond_ytm_equals_coupon():
    assert calc.price_from_ytm(100, 0.08, 5, 0.08, 2) == pytest.approx(100.0)
    assert calc.ytm_from_price(100, 100, 0.08, 5, 2) == pytest.approx(0.08, abs=1e-6)


def test_price_ytm_round_trip_and_direction():
    p = calc.price_from_ytm(100, 0.07, 10, 0.09, 2)
    assert p < 100                                         # yield above coupon: discount
    assert calc.ytm_from_price(p, 100, 0.07, 10, 2) == pytest.approx(0.09, abs=1e-6)
    assert calc.price_from_ytm(100, 0.07, 10, 0.05, 2) > 100
    assert calc.ytm_from_price(1e9, 100, 0.07, 10, 2) is None


def test_zero_coupon_duration():
    d = calc.duration(100, 0.0, 5, 0.06, 1)
    assert d["macaulay"] == pytest.approx(5.0)
    assert d["modified"] == pytest.approx(5.0 / 1.06)
    assert d["price"] == pytest.approx(100 / 1.06 ** 5)
    assert d["price_change_per_1pct"] < 0


def test_coupon_bond_duration_less_than_maturity():
    d = calc.duration(100, 0.08, 10, 0.08, 2)
    assert 0 < d["macaulay"] < 10 and d["modified"] < d["macaulay"]


def test_yields_and_tax():
    assert calc.current_yield(95, 100, 0.08) == pytest.approx(8 / 95)
    assert calc.current_yield(0, 100, 0.08) == 0.0
    assert calc.after_tax_yield(0.08, 0.30) == pytest.approx(0.056)
    assert len(calc.cashflows(100, 0.08, 3, 2)) == 6 and calc.cashflows(100, 0.08, 3, 2)[-1][1] == pytest.approx(104)
