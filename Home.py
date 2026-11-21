from pathlib import Path

import streamlit as st

from ui.common import DISCLAIMER, setup

setup("Market Understanding Lab", "📈")
st.caption("Rule-based (no AI) analysis of stocks, trading, IPOs and more, with the reasoning shown for every verdict.")

ROOT = Path(__file__).parent
MODES = [
    ("🏢", "Stock Investing", "Long-term view of any NSE stock: quality, valuation, trend, entry zone, backtest.", "1_Stock_Investing"),
    ("⚡", "Trading", "Short-term setups with stop-loss, targets, risk-based position size and costs.", "2_Trading"),
    ("🔎", "Screener", "Scan NIFTY 50 or your own list and shortlist by trend and momentum.", "3_Screener"),
    ("🆕", "IPO", "Should you apply? Score an IPO on issue structure, valuation and demand.", "4_IPO"),
    ("🏦", "Mutual Funds", "Compare funds on returns, consistency and drawdown; SIP calculators.", "5_Mutual_Funds"),
    ("🪙", "Gold & Crypto", "Trend analysis and tax notes for gold and crypto.", "6_Gold_and_Crypto"),
    ("📜", "Bonds", "Yield, duration and after-tax comparison with FDs.", "7_Bonds"),
    ("🎯", "Options (F&O)", "Learn options: payoff diagrams, Greeks. Paper only.", "8_Options_FnO"),
    ("📒", "Paper Portfolio", "Practise with virtual money and keep a trade journal.", "9_Paper_Portfolio"),
    ("📚", "Learn", "Plain-language glossary of every term used here.", "10_Learn"),
]

st.subheader("Choose a mode")
for i in range(0, len(MODES), 3):
    cols = st.columns(3)
    for col, (icon, title, desc, page) in zip(cols, MODES[i:i + 3]):
        with col.container(border=True):
            st.markdown(f"### {icon} {title}")
            st.write(desc)
            path = f"pages/{page}.py"
            if (ROOT / path).exists():
                st.page_link(path, label="Open", icon="➡️")
            else:
                st.caption("Coming soon")

st.divider()
st.subheader("How to use this")
st.markdown(
    """
1. **Check the market mood** with the Screener: are most stocks above their 200-day average?
2. **Shortlist** 5 to 10 stocks, then open each in **Stock Investing** and read the *why*, not just the verdict.
3. **Backtest** the idea on that stock with costs. If it cannot beat buy-and-hold, be sceptical.
4. For a trade, use **Trading**: it gives the stop-loss and a position size that risks only ~1% of capital.
5. **Practise in the Paper Portfolio** before using real money, and review your journal monthly.
6. Use **Learn** whenever a term is unfamiliar.
"""
)

st.subheader("Data policy")
st.markdown(
    """
- Prices come from Yahoo Finance and are **cross-checked against official NSE end-of-day data**; every page shows a *data as of* time and the result of each check.
- Free data can be wrong, late or missing. A failed check means: verify on NSE or your broker first.
- Fundamentals for Indian companies are patchy in free sources: missing values are shown as n/a and never counted as zero.
- Nothing here places orders. The app analyses; you decide and verify.
"""
)
st.caption(DISCLAIMER)
