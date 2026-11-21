"""Generates docs/architecture.png. Run: python3 docs/make_architecture.py"""
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

BLUE, ORANGE, AQUA, VIOLET, RED, GRAY = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#e34948", "#6b6b66"
INK = "#1a1a19"

fig, ax = plt.subplots(figsize=(17, 12), dpi=150)
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")


def box(x, y, w, h, title, lines=(), color=BLUE, fill="#ffffff", title_size=11, size=8.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.8", fc=fill, ec=color, lw=1.8))
    ax.text(x + w / 2, y + h - 1.5, title, ha="center", va="top", fontsize=title_size, fontweight="bold", color=color)
    for i, ln in enumerate(lines):
        ax.text(x + w / 2, y + h - 4.3 - i * 2.35, ln, ha="center", va="top", fontsize=size, color=INK)


def layer(y, h, label, color):
    ax.add_patch(FancyBboxPatch((0.8, y), 98.4, h, boxstyle="round,pad=0.1,rounding_size=1", fc=color, ec="none", alpha=0.07))
    ax.text(1.6, y + h - 1.2, label, fontsize=10, fontweight="bold", color=color, va="top")


def arrow(x1, y1, x2, y2, color=GRAY, text=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.8))
    if text:
        ax.text((x1 + x2) / 2 + 0.7, (y1 + y2) / 2, text, fontsize=8, color=color, va="center")


ax.text(50, 98.3, "Market Understanding Lab - Architecture", ha="center", fontsize=19, fontweight="bold", color=INK)
ax.text(50, 95.6, "Rule-based (no AI) analysis for Indian stocks, IPOs and more. Every score comes with the reasons behind it.",
        ha="center", fontsize=10.5, color=GRAY)

# 1. user
box(38, 88.2, 24, 5, "User (browser)", color=INK, title_size=11)

# 2. UI
layer(65.6, 21.8, "UI LAYER  -  Streamlit (Home.py, pages/, ui/)", BLUE)
pages = [("Stock Investing", "advisor report"), ("Trading", "setup + sizing"), ("Screener", "scan any list"),
         ("IPO", "calendar + verdict"), ("Mutual Funds", "score + SIP"), ("Gold & Crypto", "trend + tax"),
         ("Bonds", "YTM + duration"), ("Options F&O", "Greeks + payoff"), ("Paper Portfolio", "journal + P&L"), ("Learn", "glossary")]
for i, (t, s) in enumerate(pages):
    col, row = i % 5, i // 5
    box(2.2 + col * 19.4, 76.2 - row * 8.2, 18, 7, t, [s], color=BLUE, title_size=9.5, size=8)
ax.text(50, 66.6, "ui/common.py (demo toggle, data-quality panel, glossary hints)   |   ui/charts.py (candles, indicators, payoff)",
        ha="center", fontsize=8.8, color=BLUE)

# 3. engine
layer(38.5, 26.5, "ENGINE LAYER  -  pure Python rules, deterministic and explainable", VIOLET)
box(2.2, 50.5, 22, 11.5, "rules/advisor", ["Investing report", "Trade setup (A / B / No trade)", "Verdict + reasons + risks"], VIOLET)
box(26, 50.5, 22, 11.5, "scoring/", ["technical (trend, RSI, MACD...)", "fundamental (ROE, P/E, debt...)", "missing data = unavailable"], VIOLET)
box(49.8, 50.5, 22, 11.5, "indicators/", ["SMA, EMA, RSI, MACD", "ATR, Bollinger", "support / resistance"], VIOLET)
box(73.6, 50.5, 24, 11.5, "risk/", ["position sizing (1% rule)", "charges: STT, GST, stamp, DP", "STCG / LTCG tax estimate"], VIOLET)
box(2.2, 40, 22, 9.3, "backtest/", ["4 strategies, costs, no look-ahead", "vs buy-and-hold"], VIOLET)
box(26, 40, 22, 9.3, "portfolio/ledger", ["paper trades, avg cost, P&L", "JSON export (session only)"], VIOLET)
box(49.8, 40, 22, 9.3, "ipo/  funds/", ["IPO scoring, fund score", "SIP, XIRR, CAGR"], VIOLET)
box(73.6, 40, 24, 9.3, "derivatives/  bonds/  learn/", ["Black-Scholes, payoff, YTM", "glossary + roadmap"], VIOLET)

# 4. data
layer(17.5, 19.5, "DATA LAYER  -  fetch, validate, cross-check, timestamp", AQUA)
box(2.2, 19, 22, 14, "markets/india.py", ["NSE symbols, .NS / .BO", "Rs currency, NIFTY 50", "adapter: add US etc. later"], AQUA)
box(26, 19, 31, 14, "datasources/service.py", ["Yahoo prices  +  NSE bhavcopy", "two-source price match (1%)", "returns data + checks + as-of date"], AQUA)
box(58.8, 19, 19, 14, "core/validation", ["positive prices, high>=low", "no >40% jumps, recent"], AQUA)
box(79.5, 19, 18, 14, "core/cache + demo", ["15 min - 24 h disk cache", "synthetic demo data"], AQUA)

# 5. sources
layer(1.0, 14.5, "EXTERNAL SOURCES  (need open internet)", ORANGE)
src = [("Yahoo Finance", "prices, fundamentals\n(yfinance, unofficial)"), ("NSE archives", "bhavcopy (official EOD)\nEQUITY_L stock list"),
       ("AMFI / mfapi.in", "fund NAV + history"), ("You (CSV / form)", "IPO details from RHP"), ("Your broker / NSE", "final price check\nbefore any real order")]
for i, (t, s) in enumerate(src):
    box(2.2 + i * 19.4, 2.2, 18, 10, t, s.split("\n"), color=ORANGE if i < 4 else RED, title_size=9.5, size=8)

# arrows
arrow(50, 88.2, 50, 87.0, INK)
arrow(50, 65.6, 50, 64.6, BLUE, "calls")
arrow(50, 38.4, 50, 37.2, VIOLET, "asks for data")
arrow(50, 17.4, 50, 15.7, AQUA, "fetches")

ax.text(99, 0.2, "Educational analysis, not investment advice. Verify prices on NSE / your broker before acting.",
        ha="right", fontsize=8.2, color=GRAY, style="italic")

out = pathlib.Path(__file__).resolve().parent / "architecture.png"
fig.savefig(out, bbox_inches="tight", facecolor="white")
print("wrote", out)
