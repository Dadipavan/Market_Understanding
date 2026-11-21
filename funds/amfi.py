"""Mutual fund data: official AMFI NAV file + mfapi.in (free community API) for NAV history."""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests

from core import cache

NAV_ALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
MFAPI_URL = "https://api.mfapi.in/mf/{code}"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def parse_navall(text: str) -> pd.DataFrame:
    """AMFI file: 'Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date'."""
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(";")]
        if len(parts) >= 6 and parts[0].isdigit():
            rows.append({"code": parts[0], "name": parts[3], "nav": pd.to_numeric(parts[4], errors="coerce"), "date": parts[5]})
    return pd.DataFrame(rows, columns=["code", "name", "nav", "date"]).dropna(subset=["nav"])


def parse_mfapi(payload: dict) -> pd.Series:
    data = payload.get("data") or []
    s = pd.Series({pd.to_datetime(d["date"], format="%d-%m-%Y", errors="coerce"): pd.to_numeric(d["nav"], errors="coerce") for d in data})
    s = s[s.index.notna()].dropna().sort_index()
    return s.astype(float)


def all_schemes() -> pd.DataFrame:
    hit = cache.get("amfi:navall", 6 * 3600)
    if hit is not None:
        return hit
    r = requests.get(NAV_ALL_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    df = parse_navall(r.text)
    if df.empty:
        raise ValueError("AMFI file had no parsable schemes")
    cache.put("amfi:navall", df)
    return df


def nav_history(code: str) -> pd.Series:
    key = f"mfapi:{code}"
    hit = cache.get(key, 6 * 3600)
    if hit is not None:
        return hit["nav"]
    r = requests.get(MFAPI_URL.format(code=code), headers=HEADERS, timeout=30)
    r.raise_for_status()
    s = parse_mfapi(r.json())
    if s.empty:
        raise ValueError("No NAV history returned")
    cache.put(key, s.to_frame("nav"))
    return s


def demo_nav(code: str, years: int = 7) -> pd.Series:
    rng = np.random.default_rng(int(code[-4:] or 1) if code[-4:].isdigit() else 7)
    n = years * 252
    rets = rng.normal(0.00045, 0.009, n)
    idx = pd.bdate_range(end=pd.Timestamp.now().normalize(), periods=n)
    return pd.Series(50 * np.cumprod(1 + rets), index=idx)


def demo_schemes() -> pd.DataFrame:
    return pd.DataFrame({"code": ["900001", "900002", "900003"],
                         "name": ["DEMO Flexi Cap Fund - Direct - Growth", "DEMO Large Cap Index Fund - Direct - Growth", "DEMO Small Cap Fund - Direct - Growth"],
                         "nav": [52.1, 31.4, 88.7], "date": ["demo"] * 3})
