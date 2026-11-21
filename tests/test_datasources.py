import math

import pandas as pd
import pytest

from core.demo import demo_fundamentals, demo_prices
from core.validation import all_ok
from datasources import universe
from datasources.fundamentals import get_fundamentals, normalise
from datasources.service import get_prices
from markets.india import MARKET, NIFTY50

EQUITY_L = (
    "SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE\n"
    "RELIANCE,Reliance Industries Limited,EQ,29-NOV-1995,10,1,INE002A01018,10\n"
    "TCS,Tata Consultancy Services Limited,EQ,25-AUG-2004,1,1,INE467B01029,1\n"
    "TESTBE,Some BE Stock Ltd,BE,01-JAN-2010,10,1,INE000000001,10\n"
    "WEIRD,Odd series Ltd,XX,01-JAN-2010,10,1,INE000000002,10\n"
    "RELIANCE,Reliance Industries Limited,EQ,29-NOV-1995,10,1,INE002A01018,10\n"
)


def test_parse_equity_list_with_padded_headers():
    df = universe.parse_equity_list(EQUITY_L)
    assert list(df["symbol"]) == ["RELIANCE", "TCS", "TESTBE"]
    assert df.loc[df["symbol"] == "TCS", "name"].iloc[0] == "Tata Consultancy Services Limited"
    assert universe.parse_equity_list("FOO,BAR\n1,2\n").empty


def test_search_and_fallback():
    df = universe.parse_equity_list(EQUITY_L)
    assert list(universe.search(df, "tata")["symbol"]) == ["TCS"]
    assert list(universe.search(df, "REL")["symbol"]) == ["RELIANCE"]
    assert len(universe.search(df, "")) == 3
    fb = universe.fallback_universe()
    assert len(fb) == 50 and set(fb["symbol"]) == set(NIFTY50)


def test_normalise_fundamentals():
    info = {"longName": "Acme Ltd", "trailingPE": 20, "debtToEquity": 45.0, "returnOnEquity": 0.18, "dividendRate": 10,
            "currentPrice": 500, "heldPercentInsiders": float("nan"), "sector": "Industrials", "marketCap": "1e9"}
    n = normalise(info)
    assert n["name"] == "Acme Ltd" and n["pe"] == 20 and n["roe"] == 0.18
    assert n["debt_to_equity"] == pytest.approx(0.45)           # percent -> ratio
    assert n["dividend_yield"] == pytest.approx(0.02)
    assert n["promoter_holding"] is None                          # NaN dropped, never zero
    assert n["market_cap"] == 1e9
    assert n["revenue_growth"] is None and n["beta"] is None
    empty = normalise({})
    assert all(v is None for k, v in empty.items() if k != "source")


def test_demo_fundamentals_via_getter():
    f = get_fundamentals("INFY", demo=True)
    assert f == demo_fundamentals("INFY") and f["source"].startswith("DEMO")
    assert get_fundamentals("INFY", demo=True) == f      # deterministic


def test_demo_prices_deterministic_and_valid():
    a, b = demo_prices("TCS", "1y"), demo_prices("TCS", "1y")
    assert a.equals(b) and not a.equals(demo_prices("INFY", "1y"))
    assert len(a) == 252 and (a["High"] >= a["Low"]).all() and (a["Close"] > 0).all()
    assert (a["High"] >= a[["Open", "Close"]].max(axis=1) - 1e-9).all()


def test_service_demo_mode_is_verified_and_labelled():
    res = get_prices("RELIANCE", "1y", demo=True)
    assert res.demo and res.verified and all_ok(res.checks)
    assert "DEMO" in res.sources[0] and res.as_of


def test_market_symbol_mapping():
    assert MARKET.to_yahoo("reliance") == "RELIANCE.NS"
    assert MARKET.to_yahoo(" m&m ") == "M&M.NS"
    assert MARKET.to_yahoo("^NSEI") == "^NSEI"
    assert MARKET.to_yahoo("532540.BO") == "532540.BO"
    assert MARKET.to_yahoo("TCS.NS") == "TCS.NS"
    assert MARKET.from_yahoo("TCS.NS") == "TCS" and MARKET.from_yahoo("532540.BO") == "532540"
    assert len(MARKET.universe()) == 50 and len(set(NIFTY50)) == 50
