"""Tiny on-disk cache with a time-to-live, so we don't hammer free data sources."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"


def _path(key: str) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    return CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest() + ".pkl")


def get(key: str, ttl_seconds: int) -> pd.DataFrame | None:
    p = _path(key)
    if p.exists() and time.time() - p.stat().st_mtime < ttl_seconds:
        return pd.read_pickle(p)
    return None


def put(key: str, df: pd.DataFrame) -> None:
    df.to_pickle(_path(key))
