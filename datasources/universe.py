"""List of all NSE-listed equities (official file), with a safe fallback."""
from __future__ import annotations

import io

import pandas as pd
import requests

from core import cache
from markets.india import NIFTY50

URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
TTL = 24 * 3600


def fallback_universe() -> pd.DataFrame:
    return pd.DataFrame({"symbol": NIFTY50, "name": NIFTY50})


def parse_equity_list(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip() for c in df.columns]
    if "SYMBOL" not in df.columns:
        return pd.DataFrame()
    name_col = "NAME OF COMPANY" if "NAME OF COMPANY" in df.columns else "SYMBOL"
    if "SERIES" in df.columns:
        df = df[df["SERIES"].astype(str).str.strip().isin(["EQ", "BE", "BZ", "SM", "ST"])]
    out = pd.DataFrame({"symbol": df["SYMBOL"].astype(str).str.strip(), "name": df[name_col].astype(str).str.strip()})
    return out.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)


def all_nse_equities() -> tuple[pd.DataFrame, bool]:
    """Returns (universe, is_full_list). Falls back to NIFTY 50 if NSE is unreachable."""
    hit = cache.get("nse:equity_l", TTL)
    if hit is not None and not hit.empty:
        return hit, True
    try:
        r = requests.get(URL, headers=HEADERS, timeout=15)
        if r.status_code == 200 and r.content and len(r.content) < 10_000_000:
            df = parse_equity_list(r.text)
            if len(df) > 100:
                cache.put("nse:equity_l", df)
                return df, True
    except requests.RequestException:
        pass
    return fallback_universe(), False


def search(df: pd.DataFrame, query: str, limit: int = 50) -> pd.DataFrame:
    q = query.strip().lower()
    if not q:
        return df.head(limit)
    m = df["symbol"].str.lower().str.contains(q, regex=False) | df["name"].str.lower().str.contains(q, regex=False)
    return df[m].head(limit)
