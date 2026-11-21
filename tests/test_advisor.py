import pytest

from core.demo import demo_fundamentals, demo_prices
from rules.advisor import investing_report, trading_setup

STRONG = {"roe": 0.25, "profit_margin": 0.2, "operating_margin": 0.3, "revenue_growth": 0.2, "earnings_growth": 0.25,
          "debt_to_equity": 0.1, "current_ratio": 2.0, "pe": 18.0, "promoter_holding": 0.55, "sector": "Technology"}


def test_investing_report_with_fundamentals():
    df = demo_prices("RELIANCE", "2y")
    rep = investing_report("RELIANCE", df, demo_fundamentals("RELIANCE"))
    assert 0 <= rep.score <= 100
    assert rep.fundamental is not None
    assert rep.level in {"success", "warning", "error", "info"}
    assert rep.summary
    assert rep.entry_zone is not None and rep.entry_zone[0] <= rep.entry_zone[1]
    assert rep.invalidation is not None and rep.invalidation < float(df["Close"].iloc[-1])
    assert not rep.verdict.startswith("UNVERIFIED")


def test_score_is_weighted_60_40():
    df = demo_prices("WEIGHT", "2y")
    rep = investing_report("WEIGHT", df, STRONG)
    assert rep.fundamental is not None
    assert rep.score == pytest.approx(round(0.6 * rep.fundamental.score + 0.4 * rep.technical.score, 1))


def test_without_fundamentals_never_strong():
    df = demo_prices("NOFUND", "2y")
    rep = investing_report("NOFUND", df, None)
    assert rep.fundamental is None
    assert not rep.verdict.startswith(("Strong", "Good"))
    assert rep.score == pytest.approx(rep.technical.score)
    assert any("Fundamentals missing" in r for r in rep.risks)


def test_sparse_fundamentals_treated_as_missing():
    rep = investing_report("SPARSE", demo_prices("SPARSE", "2y"), {"roe": 0.2})
    assert rep.fundamental is None  # coverage below 40%


def test_unverified_data_prefix():
    rep = investing_report("UNV", demo_prices("UNV", "2y"), STRONG, verified=False)
    assert rep.verdict.startswith("UNVERIFIED DATA - ")
    assert rep.level != "success"
    assert any("quality checks" in r for r in rep.risks)


def test_trading_setup_invariants():
    df = demo_prices("TRADE", "1y")
    s = trading_setup("TRADE", df, capital=500_000, risk_pct=1.0)
    assert s is not None
    assert s.stop < s.entry < s.target1 < s.target2
    assert s.risk_reward_t1 == pytest.approx(2.0, abs=0.02)
    q = s.sizing["qty"]
    assert q >= 0
    assert q * (s.entry - s.stop) <= 500_000 * 0.01 + 1e-6
    assert q * s.entry <= 500_000 + 1e-6
    assert s.grade in {"A", "B", "No trade"}


def test_trading_grade_matches_score():
    for sym in ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]:
        s = trading_setup(sym, demo_prices(sym, "1y"), 100_000)
        if s.score >= 70:
            assert s.grade == "A"
        elif s.score >= 55:
            assert s.grade == "B"
        else:
            assert s.grade == "No trade"


def test_trading_tiny_capital_gives_zero_qty():
    s = trading_setup("TRADE", demo_prices("TRADE", "1y"), capital=10, risk_pct=1.0)
    assert s.sizing["qty"] == 0
    assert s.costs_t1 is None
    assert s.notes


def test_trading_max_position_cap():
    s = trading_setup("CAP", demo_prices("CAP", "1y"), capital=1_000_000, risk_pct=5.0, max_position_pct=10.0)
    assert s.sizing["capital_used"] <= 1_000_000 * 0.10 + s.entry


def test_trading_needs_enough_data():
    assert trading_setup("X", demo_prices("X", "1mo").head(10), 100_000) is None
