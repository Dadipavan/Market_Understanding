import pytest

from portfolio.ledger import Ledger
from risk.costs import trade_costs


def test_buy_updates_cash_and_avg_cost():
    led = Ledger(starting_cash=100_000)
    t1 = led.add_trade("2026-01-01", "tcs", "buy", 100, 100.0)
    t2 = led.add_trade("2026-01-02", "TCS", "buy", 100, 120.0)
    cash, hold = led.state()
    assert hold["TCS"]["qty"] == 200 and hold["TCS"]["avg"] == pytest.approx(110.0)
    assert cash == pytest.approx(100_000 - 100 * 100 - 100 * 120 - t1["fees"] - t2["fees"])
    assert t1["fees"] == trade_costs(100.0, 100, "buy", "delivery")


def test_sell_realised_pnl_and_close_position():
    led = Ledger(starting_cash=100_000)
    led.add_trade("2026-01-01", "INFY", "buy", 100, 100.0)
    s = led.add_trade("2026-02-01", "INFY", "sell", 40, 110.0)
    assert s["realised"] == pytest.approx((110 - 100) * 40 - s["fees"])
    _, hold = led.state()
    assert hold["INFY"]["qty"] == 60 and hold["INFY"]["avg"] == pytest.approx(100.0)
    led.add_trade("2026-03-01", "INFY", "sell", 60, 90.0)
    _, hold = led.state()
    assert "INFY" not in hold


def test_errors_do_not_mutate():
    led = Ledger(starting_cash=1_000)
    with pytest.raises(ValueError, match="Not enough cash"):
        led.add_trade("2026-01-01", "A", "buy", 100, 100.0)
    with pytest.raises(ValueError, match="Cannot sell"):
        led.add_trade("2026-01-01", "A", "sell", 1, 100.0)
    led.add_trade("2026-01-01", "A", "buy", 5, 100.0)
    with pytest.raises(ValueError, match="Cannot sell"):
        led.add_trade("2026-01-02", "A", "sell", 6, 100.0)
    with pytest.raises(ValueError):
        led.add_trade("2026-01-02", "A", "buy", 0, 100.0)
    with pytest.raises(ValueError):
        led.add_trade("2026-01-02", "A", "short", 1, 100.0)
    assert len(led.trades) == 1


def test_json_round_trip():
    led = Ledger(starting_cash=500_000)
    led.add_trade("2026-01-01", "RELIANCE", "buy", 50, 2500.0, stop=2400.0, target=2700.0, note="breakout")
    led.add_trade("2026-01-10", "RELIANCE", "sell", 20, 2600.0)
    led2 = Ledger.from_json(led.to_json())
    assert led2.starting_cash == led.starting_cash
    assert led2.state() == led.state()
    assert led2.trades == led.trades


def test_from_json_rejects_invalid_history():
    bad = '{"starting_cash": 100, "trades": [{"symbol": "X", "side": "buy", "qty": 10, "price": 100.0, "fees": 0}]}'
    with pytest.raises(ValueError):
        Ledger.from_json(bad)


def test_summary_and_holdings():
    led = Ledger(starting_cash=100_000)
    led.add_trade("2026-01-01", "A", "buy", 100, 100.0)
    led.add_trade("2026-01-05", "A", "sell", 50, 120.0)   # win
    led.add_trade("2026-01-06", "B", "buy", 100, 50.0)
    led.add_trade("2026-01-07", "B", "sell", 100, 40.0)   # loss
    s = led.summary({"A": 110.0})
    assert s["closed_trades"] == 2 and s["win_rate"] == pytest.approx(0.5)
    assert s["avg_win"] > 0 > s["avg_loss"]
    assert s["equity"] == pytest.approx(s["cash"] + 50 * 110.0)
    assert s["fees_paid"] == pytest.approx(sum(t["fees"] for t in led.trades), abs=0.01)
    assert s["realised_pnl"] == pytest.approx(sum(t["realised"] for t in led.trades if t["side"] == "sell"), abs=0.01)
    table = led.holdings_table({"A": 110.0})
    assert list(table["symbol"]) == ["A"] and table["unrealised"].iloc[0] == pytest.approx(500.0)
    assert table["unrealised_pct"].iloc[0] == pytest.approx(10.0)
    assert not led.trades_df().empty


def test_empty_ledger():
    led = Ledger(starting_cash=10_000)
    s = led.summary({})
    assert s["equity"] == 10_000 and s["win_rate"] == 0.0 and s["concentration_pct"] == 0.0
    assert led.holdings_table({}).empty
