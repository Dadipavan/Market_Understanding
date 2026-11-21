"""The live-data path (Yahoo + NSE cross-check) exercised offline with mocked fetchers."""
import datetime as dt

import pandas as pd
import pytest

from core.demo import demo_prices
from datasources import nse, service, yahoo
from datasources.yahoo import DataSourceError


def tz_frame() -> pd.DataFrame:
    df = demo_prices("TCS", "1y")
    df.index = df.index.tz_localize("Asia/Kolkata")     # yfinance returns tz-aware IST timestamps
    return df


def bhav(symbol: str, close: float) -> pd.DataFrame:
    b = pd.DataFrame({"Open": [close], "High": [close], "Low": [close], "Close": [close], "Volume": [1]}, index=[symbol])
    return b


@pytest.fixture
def patched(monkeypatch):
    df = tz_frame()
    monkeypatch.setattr(yahoo, "fetch_history", lambda sym, period="1y", interval="1d": df)
    return df


def test_cross_check_passes_when_prices_agree(monkeypatch, patched):
    day = patched.index[-1].date()
    close = float(patched["Close"].iloc[-1])
    monkeypatch.setattr(nse, "latest_bhavcopy", lambda max_lookback=7: (day, bhav("TCS", close * 1.002)))
    res = service.get_prices("tcs", "1y")
    c = [x for x in res.checks if x.name == "two-source price match"][0]
    assert c.ok, c.detail
    assert res.verified, [x for x in res.checks if not x.ok]
    assert any("NSE bhavcopy" in s for s in res.sources) and res.as_of == f"{patched.index[-1]:%Y-%m-%d}"


def test_cross_check_fails_when_prices_disagree(monkeypatch, patched):
    day = patched.index[-1].date()
    close = float(patched["Close"].iloc[-1])
    monkeypatch.setattr(nse, "latest_bhavcopy", lambda max_lookback=7: (day, bhav("TCS", close * 1.10)))
    res = service.get_prices("TCS", "1y")
    c = [x for x in res.checks if x.name == "two-source price match"][0]
    assert not c.ok and not res.verified


def test_cross_check_flags_when_nse_unavailable_or_symbol_missing(monkeypatch, patched):
    monkeypatch.setattr(nse, "latest_bhavcopy", lambda max_lookback=7: None)
    res = service.get_prices("TCS", "1y")
    assert any(x.name == "two-source price match" and not x.ok for x in res.checks)
    day = patched.index[-1].date()
    monkeypatch.setattr(nse, "latest_bhavcopy", lambda max_lookback=7: (day, bhav("OTHER", 1.0)))
    res = service.get_prices("TCS", "1y")
    c = [x for x in res.checks if x.name == "two-source price match"][0]
    assert not c.ok and "not found" in c.detail


def test_nse_date_not_in_yahoo_history(monkeypatch, patched):
    far = dt.date(2030, 1, 1)
    monkeypatch.setattr(nse, "latest_bhavcopy", lambda max_lookback=7: (far, bhav("TCS", 100.0)))
    res = service.get_prices("TCS", "1y")
    assert any(x.name == "two-source price match" and not x.ok for x in res.checks)


def test_raw_and_index_symbols_skip_cross_check(monkeypatch, patched):
    def boom(*a, **k):
        raise AssertionError("NSE must not be called")
    monkeypatch.setattr(nse, "latest_bhavcopy", boom)
    for sym, raw in (("BTC-INR", True), ("^NSEI", False), ("GOLDBEES.NS", True)):
        res = service.get_prices(sym, "1y", raw=raw)
        assert not any(x.name == "two-source price match" for x in res.checks)
    assert not any(x.name == "two-source price match" for x in service.get_prices("532540.BO", "1y").checks)
    assert not any(x.name == "two-source price match" for x in service.get_prices("TCS", "1y", cross_verify=False).checks)


def test_yahoo_failure_returns_clean_result(monkeypatch):
    def fail(*a, **k):
        raise DataSourceError("Yahoo Finance unreachable: DNSError")
    monkeypatch.setattr(yahoo, "fetch_history", fail)
    res = service.get_prices("TCS", "1y")
    assert res.df.empty and not res.verified
    assert res.checks[0].name == "data source reachable" and "DNSError" in res.checks[0].detail


def test_empty_history(monkeypatch):
    monkeypatch.setattr(yahoo, "fetch_history", lambda *a, **k: pd.DataFrame())
    res = service.get_prices("NOSUCH", "1y")
    assert res.df.empty and not res.verified


def test_nse_bhavcopy_parsing(monkeypatch, tmp_path):
    import io, zipfile
    csv = ("TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n"
           "TCS,EQ,100,110,95,105,1000\nJUNK,BE,1,1,1,1,1\n")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("bhav.csv", csv)

    class R:
        status_code, content = 200, buf.getvalue()

    monkeypatch.setattr(nse.requests, "get", lambda *a, **k: R())
    monkeypatch.setattr(nse.cache, "get", lambda *a, **k: None)
    monkeypatch.setattr(nse.cache, "put", lambda *a, **k: None)
    df = nse.fetch_bhavcopy(dt.date(2026, 11, 20))
    assert list(df.index) == ["TCS"] and df.loc["TCS", "Close"] == 105

    class Bad:
        status_code, content = 200, b"not a zip"
    monkeypatch.setattr(nse.requests, "get", lambda *a, **k: Bad())
    assert nse.fetch_bhavcopy(dt.date(2026, 11, 19)).empty
