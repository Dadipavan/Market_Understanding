from pathlib import Path

import pandas as pd
import pytest

from ipo.scoring import analyse_ipo, application_amount, clean, estimated_listing_price, status

SAMPLE = Path(__file__).resolve().parent.parent / "ipo" / "ipos_sample.csv"


@pytest.fixture
def ipos():
    return clean(pd.read_csv(SAMPLE))


def test_clean_types(ipos):
    assert len(ipos) == 3
    assert pd.api.types.is_datetime64_any_dtype(ipos["open_date"])
    assert pd.api.types.is_float_dtype(ipos["qib_x"])
    assert ipos["sample"].all()
    assert list(ipos["exchange"]) == ["Mainboard", "Mainboard", "SME"]


def test_clean_adds_missing_columns_and_drops_unnamed():
    df = clean(pd.DataFrame({"name": ["X", None], "issue_pe": ["12", "abc"]}))
    assert len(df) == 1 and df["issue_pe"].iloc[0] == 12
    assert "gmp_pct" in df.columns and df["exchange"].iloc[0] == "Mainboard"


def test_status_lifecycle(ipos):
    row = ipos.iloc[0]  # opens 2026-12-01, closes 12-03, lists 12-08
    assert status(row, pd.Timestamp("2026-11-21")) == "Upcoming"
    assert status(row, pd.Timestamp("2026-12-02")) == "Open"
    assert status(row, pd.Timestamp("2026-12-03")) == "Open"
    assert status(row, pd.Timestamp("2026-12-05")).startswith("Closed")
    assert status(row, pd.Timestamp("2026-12-09")) == "Listed"


def test_sample_verdicts(ipos):
    alpha, cov_a = analyse_ipo(ipos.iloc[0])
    assert alpha.score == pytest.approx(100.0) and alpha.verdict == "Apply" and cov_a == pytest.approx(1.0)
    beta, _ = analyse_ipo(ipos.iloc[1])
    assert beta.verdict == "Avoid" and beta.score < 30
    assert any("Loss-making" in r for r in beta.risks) and any("Offer for Sale" in r for r in beta.risks)


def test_sme_is_capped_at_caution(ipos):
    gamma, cov = analyse_ipo(ipos.iloc[2])
    assert gamma.score >= 70  # would be "Apply" for a mainboard issue
    assert gamma.verdict == "Apply with caution"
    assert any("SME" in r for r in gamma.risks)
    unavailable = {r.rule for r in gamma.reasons if not r.available}
    assert unavailable == {"Institutional demand (QIB)", "Grey-market sentiment (GMP)"}
    assert cov == pytest.approx(0.85)


def test_insufficient_data():
    row = clean(pd.DataFrame({"name": ["Sparse"], "gmp_pct": [12]})).iloc[0]
    a, cov = analyse_ipo(row)
    assert a.verdict == "Insufficient data" and cov < 0.5


def test_expensive_valuation_scores_zero_on_that_rule(ipos):
    row = ipos.iloc[0].copy()
    row["issue_pe"] = 50.0
    a, _ = analyse_ipo(row)
    by = {r.rule: r for r in a.reasons}
    assert by["Valuation vs listed peers"].points == 0
    assert a.score == pytest.approx(80.0)


def test_application_amount_and_listing_estimate(ipos):
    row = ipos.iloc[0]
    assert application_amount(row) == pytest.approx(295 * 50)
    assert application_amount(row, lots=2) == pytest.approx(295 * 50 * 2)
    assert estimated_listing_price(row) == pytest.approx(295 * 1.18)
    assert estimated_listing_price(ipos.iloc[2]) is None
