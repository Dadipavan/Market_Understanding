import pytest

from core.demo import demo_fundamentals, demo_prices
from scoring.fundamental import fundamental_analysis
from scoring.technical import technical_analysis


def test_technical_full_history():
    a, ind, cov = technical_analysis(demo_prices("AAA", "2y"))
    assert 0 <= a.score <= 100
    assert cov == pytest.approx(1.0)
    assert a.verdict in {"Bullish", "Neutral", "Bearish"}
    assert all(r.available for r in a.reasons)
    assert sum(r.max_points for r in a.reasons) == pytest.approx(100)
    assert not ind.empty


def test_technical_short_history_marks_unavailable_not_zero():
    a, ind, cov = technical_analysis(demo_prices("AAA", "3mo"))  # 66 bars: no 200-day average
    unavailable = [r for r in a.reasons if not r.available]
    assert {r.rule for r in unavailable} >= {"Long-term trend", "Medium vs long trend"}
    assert all(r.points == 0 for r in unavailable)
    assert 0 < cov < 1
    # score is computed only on rules that could be evaluated
    avail = [r for r in a.reasons if r.available]
    expected = sum(r.points for r in avail) / sum(r.max_points for r in avail) * 100
    assert a.score == pytest.approx(round(expected, 1))
    assert any("Only" in x for x in a.risks) or cov >= 0.7


def test_technical_too_little_data():
    a, ind, cov = technical_analysis(demo_prices("AAA", "1mo").head(20))
    assert a.verdict == "Not enough data" and cov == 0.0 and ind.empty


def test_fundamental_demo_info():
    a, cov = fundamental_analysis(demo_fundamentals("INFY"))
    assert 0 <= a.score <= 100
    assert cov > 0.8
    assert a.verdict in {"Strong", "Average", "Weak"}


def test_fundamental_missing_everything():
    a, cov = fundamental_analysis(None)
    assert a.verdict == "Fundamentals unavailable" and cov == 0.0
    a, cov = fundamental_analysis({})
    assert a.verdict == "Fundamentals unavailable"


def test_fundamental_partial_data_is_unavailable_not_zero():
    a, cov = fundamental_analysis({"roe": 0.20, "sector": "Technology"})
    by = {r.rule: r for r in a.reasons}
    assert by["Return on equity"].available and by["Return on equity"].points == 15
    assert not by["Net profit margin"].available
    assert 0 < cov < 0.5
    assert a.score == pytest.approx(100.0)  # perfect on the only evaluated rule
    assert any("Only" in r for r in a.risks)


def test_financial_sector_skips_debt_rules():
    info = {"sector": "Financial Services", "debt_to_equity": 6.0, "current_ratio": 0.5, "roe": 0.16}
    a, _ = fundamental_analysis(info)
    by = {r.rule: r for r in a.reasons}
    assert not by["Debt / equity"].available
    assert not by["Short-term liquidity"].available
    assert not any("High debt" in r for r in a.risks)
    a2, _ = fundamental_analysis({**info, "sector": "Industrials"})
    by2 = {r.rule: r for r in a2.reasons}
    assert by2["Debt / equity"].available and by2["Debt / equity"].points == 0
    assert any("High debt" in r for r in a2.risks)


def test_fundamental_loss_making_and_expensive():
    a, _ = fundamental_analysis({"pe": -5.0, "roe": 0.01, "sector": "Technology"})
    assert any("loss-making" in r.lower() for r in a.risks)
    b, _ = fundamental_analysis({"pe": 80.0, "sector": "Technology"})
    assert any("Very high P/E" in r for r in b.risks)


def test_strong_company_scores_high():
    info = {"roe": 0.25, "profit_margin": 0.2, "operating_margin": 0.3, "revenue_growth": 0.2, "earnings_growth": 0.25,
            "debt_to_equity": 0.1, "current_ratio": 2.0, "pe": 18.0, "promoter_holding": 0.55, "sector": "Technology"}
    a, cov = fundamental_analysis(info)
    assert a.score == pytest.approx(100.0) and a.verdict == "Strong" and cov == pytest.approx(1.0)
