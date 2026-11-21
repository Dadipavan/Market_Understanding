"""Data-quality checks. Free data can be wrong, so every dataset is checked
before it is shown, and the result is displayed to the user."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def validate_ohlcv(
    df: pd.DataFrame,
    max_jump: float = 0.40,
    max_stale_days: int = 5,
    today: pd.Timestamp | None = None,
) -> list[Check]:
    """Sanity-check an OHLCV frame (index = dates)."""
    checks: list[Check] = []
    if df is None or df.empty:
        return [Check("data present", False, "No data returned")]

    cols = {"Open", "High", "Low", "Close", "Volume"}
    missing = cols - set(df.columns)
    if missing:
        return [Check("columns", False, f"Missing columns: {sorted(missing)}")]

    checks.append(Check("data present", True, f"{len(df)} rows"))

    nulls = int(df[["Open", "High", "Low", "Close"]].isna().sum().sum())
    checks.append(Check("no missing prices", nulls == 0, f"{nulls} missing values"))

    prices = df[["Open", "High", "Low", "Close"]]
    nonpos = int((prices <= 0).sum().sum())
    checks.append(Check("prices positive", nonpos == 0, f"{nonpos} non-positive values"))

    bad_hl = int((df["High"] < df["Low"]).sum())
    checks.append(Check("high >= low", bad_hl == 0, f"{bad_hl} bad rows"))

    out_of_range = int(
        ((df["Close"] > df["High"] * 1.0001) | (df["Close"] < df["Low"] * 0.9999)).sum()
    )
    checks.append(Check("close within day range", out_of_range == 0, f"{out_of_range} bad rows"))

    jumps = df["Close"].pct_change().abs()
    big = jumps[jumps > max_jump]
    detail = (
        "none"
        if big.empty
        else "; ".join(f"{d:%Y-%m-%d} ({v:.0%})" for d, v in big.head(3).items())
        + " - check for split/bonus or bad tick"
    )
    checks.append(Check(f"no jumps over {max_jump:.0%}", big.empty, detail))

    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        checks.append(Check("dates ordered & unique", False, "Index unsorted or duplicated"))
    else:
        checks.append(Check("dates ordered & unique", True, "ok"))

    now = today if today is not None else pd.Timestamp.now(tz=df.index.tz).normalize()
    last = df.index[-1]
    age = (now - last.normalize()).days
    checks.append(Check("data is recent", age <= max_stale_days, f"last row {last:%Y-%m-%d} ({age} days old)"))
    return checks


def cross_check(name_a: str, price_a: float, name_b: str, price_b: float, tol: float = 0.01) -> Check:
    """Compare the same price from two independent sources."""
    if price_a is None or price_b is None or price_a <= 0 or price_b <= 0:
        return Check("two-source price match", False, "One source has no price")
    diff = abs(price_a - price_b) / price_b
    return Check(
        "two-source price match",
        diff <= tol,
        f"{name_a} {price_a:.2f} vs {name_b} {price_b:.2f} (diff {diff:.2%}, tolerance {tol:.0%})",
    )


def all_ok(checks: list[Check]) -> bool:
    return all(c.ok for c in checks)
