"""India (NSE) market adapter: everything market-specific lives here so other
markets can be added later as sibling modules with the same interface."""
from __future__ import annotations

from dataclasses import dataclass

# NIFTY 50 constituents. The index is reconstituted twice a year, so verify
# against https://www.niftyindices.com before relying on this list.
NIFTY50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY",
    "ITC", "JIOFIN", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NESTLEIND", "NTPC", "ONGC",
    "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SHRIRAMFIN",
    "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
]


@dataclass(frozen=True)
class IndiaMarket:
    name: str = "India (NSE)"
    currency: str = "₹"
    timezone: str = "Asia/Kolkata"
    yahoo_suffix: str = ".NS"
    index_symbol: str = "^NSEI"

    def to_yahoo(self, symbol: str) -> str:
        symbol = symbol.strip().upper()
        if symbol.startswith("^") or symbol.endswith((".NS", ".BO")):
            return symbol
        return symbol + self.yahoo_suffix

    def from_yahoo(self, symbol: str) -> str:
        return symbol.removesuffix(".NS").removesuffix(".BO")

    def universe(self) -> list[str]:
        return list(NIFTY50)


MARKET = IndiaMarket()
