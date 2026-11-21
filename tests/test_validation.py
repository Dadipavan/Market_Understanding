import pandas as pd

from core.validation import all_ok, cross_check, validate_ohlcv


def frame(rows, start="2026-11-16"):
    idx = pd.date_range(start, periods=len(rows), freq="D")
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close", "Volume"], index=idx)


TODAY = pd.Timestamp("2026-11-21")
GOOD = [(100, 105, 99, 102, 1000), (102, 106, 101, 104, 1100), (104, 108, 103, 107, 900)]


def test_good_data_passes():
    assert all_ok(validate_ohlcv(frame(GOOD), today=TODAY))


def test_empty_fails():
    assert not all_ok(validate_ohlcv(pd.DataFrame()))


def test_big_jump_flagged():
    rows = GOOD + [(200, 210, 195, 205, 1000)]
    checks = {c.name: c for c in validate_ohlcv(frame(rows), today=TODAY)}
    assert not checks["no jumps over 40%"].ok


def test_high_below_low_flagged():
    rows = GOOD + [(100, 90, 99, 95, 1000)]
    checks = {c.name: c for c in validate_ohlcv(frame(rows), today=TODAY)}
    assert not checks["high >= low"].ok


def test_stale_flagged():
    checks = {c.name: c for c in validate_ohlcv(frame(GOOD), today=pd.Timestamp("2026-12-30"))}
    assert not checks["data is recent"].ok


def test_cross_check_within_and_outside_tolerance():
    assert cross_check("A", 100.5, "B", 100.0).ok
    assert not cross_check("A", 105.0, "B", 100.0).ok
    assert not cross_check("A", None, "B", 100.0).ok
