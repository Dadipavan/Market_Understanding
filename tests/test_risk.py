import pytest

from risk.costs import capital_gains_tax, round_trip, trade_costs
from risk.sizing import position_size


def test_delivery_buy_and_sell_costs():
    # turnover 10,000: exchange 0.297 + sebi 0.01 + gst 0.05526 + STT 10 + stamp 1.5
    assert trade_costs(100, 100, "buy", "delivery") == pytest.approx(11.86, abs=0.01)
    # sell: no stamp, DP charge 15.34
    assert trade_costs(100, 100, "sell", "delivery") == pytest.approx(25.70, abs=0.01)


def test_intraday_costs():
    assert trade_costs(100, 100, "sell", "intraday") == pytest.approx(2.86, abs=0.01)
    assert trade_costs(100, 100, "buy", "intraday") == pytest.approx(0.66, abs=0.01)


def test_brokerage_adds_gst():
    base = trade_costs(100, 100, "buy", "intraday", brokerage=0.0)
    with_b = trade_costs(100, 100, "buy", "intraday", brokerage=20.0)
    assert with_b - base == pytest.approx(20 * 1.18, abs=0.01)


def test_round_trip():
    rt = round_trip(100, 110, 100)
    assert rt["gross_pnl"] == pytest.approx(1000.0)
    assert rt["costs"] == pytest.approx(38.60, abs=0.02)
    assert rt["net_pnl"] == pytest.approx(961.40, abs=0.02)
    assert rt["breakeven_move_pct"] == pytest.approx(0.386, abs=0.001)


def test_capital_gains_tax():
    st = capital_gains_tax(100_000, 100)
    assert st["type"] == "STCG" and st["tax"] == pytest.approx(100_000 * 0.20 * 1.04)
    lt = capital_gains_tax(225_000, 400)
    assert lt["type"] == "LTCG" and lt["taxable"] == pytest.approx(100_000) and lt["tax"] == pytest.approx(13_000)
    assert capital_gains_tax(100_000, 400)["tax"] == 0.0  # under the exemption
    assert capital_gains_tax(-500, 10)["type"] == "loss"
    assert capital_gains_tax(1000, 365)["type"] == "STCG" and capital_gains_tax(1000, 366)["type"] == "LTCG"


def test_position_size_by_risk():
    p = position_size(100_000, 1.0, 100, 95)
    assert p["qty"] == 200 and p["capital_used"] == pytest.approx(20_000) and p["risk_amount"] == pytest.approx(1000)


def test_position_size_capped_by_capital():
    p = position_size(10_000, 5.0, 100, 99)
    assert p["qty"] == 100 and "capital" in p["note"].lower()


def test_position_size_invalid_and_tiny():
    assert position_size(100_000, 1.0, 100, 100)["qty"] == 0
    assert position_size(100_000, 1.0, 100, 105)["qty"] == 0
    assert position_size(0, 1.0, 100, 95)["qty"] == 0
    tiny = position_size(100, 1.0, 1000, 900)
    assert tiny["qty"] == 0 and tiny["note"]


def test_position_size_max_position_pct():
    p = position_size(100_000, 5.0, 100, 99, max_position_pct=10)
    assert p["qty"] == 100
