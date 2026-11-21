"""Official NSE end-of-day data (CM bhavcopy, UDiFF format).

The downloaded zip is untrusted input: it is parsed in memory as CSV only and
never written to disk or executed.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, timedelta

import pandas as pd
import requests

from core import cache

URL = "https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d}_F_0000.csv.zip"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
TTL = 24 * 3600
MAX_BYTES = 20 * 1024 * 1024


def fetch_bhavcopy(day: date) -> pd.DataFrame:
    """Return EQ-series closes for one date, indexed by symbol. Empty if no data."""
    key = f"nse:bhav:{day:%Y%m%d}"
    hit = cache.get(key, TTL * 30)
    if hit is not None:
        return hit
    try:
        r = requests.get(URL.format(d=f"{day:%Y%m%d}"), headers=HEADERS, timeout=15)
    except requests.RequestException:
        return pd.DataFrame()
    if r.status_code != 200 or not r.content or len(r.content) > MAX_BYTES:
        return pd.DataFrame()
    try:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not names:
                return pd.DataFrame()
            df = pd.read_csv(z.open(names[0]))
    except (zipfile.BadZipFile, pd.errors.ParserError, ValueError):
        return pd.DataFrame()
    df = df[df["SctySrs"] == "EQ"]
    out = pd.DataFrame(
        {
            "Open": df["OpnPric"], "High": df["HghPric"], "Low": df["LwPric"],
            "Close": df["ClsPric"], "Volume": df["TtlTradgVol"],
        }
    )
    out.index = df["TckrSymb"].values
    out.attrs["date"] = day
    cache.put(key, out)
    return out


def latest_bhavcopy(max_lookback: int = 7) -> tuple[date, pd.DataFrame] | None:
    """Walk back from today to the most recent trading day with published data."""
    d = date.today()
    for _ in range(max_lookback):
        if d.weekday() < 5:
            df = fetch_bhavcopy(d)
            if not df.empty:
                return d, df
        d -= timedelta(days=1)
    return None
