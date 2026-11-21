import math

import pandas as pd
import streamlit as st

from backtest.engine import STRATEGIES, run_backtest
from datasources.service import get_prices
from scoring.technical import technical_analysis
from ui import charts
from ui.common import level_box, pct, setup, show_checks, term

demo = setup("Gold & Crypto", "🪙")
st.caption("Trend and risk analysis for gold and crypto price series. These assets have no earnings, so there are no "
           "fundamental scores here: only price behaviour, risk and a historical backtest.")


def reasons_table(reasons) -> pd.DataFrame:
    rows = []
    for r in reasons:
        status = "n/a" if not r.available else ("✅" if r.passed else "❌")
        rows.append({"Rule": r.rule, "Result": status, "Points": f"{r.points:.0f}/{r.max_points:.0f}", "Why": r.detail})
    return pd.DataFrame(rows)


def asset_panel(key: str, label: str, presets: list[str], ann_days: int, default_cost: float) -> None:
    c1, c2, c3 = st.columns([2, 2, 1])
    choice = c1.selectbox(f"{label} instrument", presets + ["Custom Yahoo symbol"], key=f"{key}_choice")
    custom = ""
    if choice == "Custom Yahoo symbol":
        custom = c2.text_input("Yahoo Finance symbol (e.g. GC=F, SOL-INR)", key=f"{key}_custom").strip()
    period = c3.selectbox("Period", ["6mo", "1y", "2y", "5y"], index=2, key=f"{key}_period")
    sym = custom if choice == "Custom Yahoo symbol" else choice
    if not sym:
        st.info("Enter a Yahoo Finance symbol to continue.")
        return

    with st.spinner(f"Fetching {sym}..."):
        res = get_prices(sym, period, demo=demo, raw=True)
    if res.df.empty:
        st.error(f"No data for {sym}.")
        for c in res.checks:
            st.write(f"❌ **{c.name}**: {c.detail}")
        st.caption("Check the symbol, your network, or whether this instrument exists on Yahoo Finance.")
        return

    df = res.df
    close = df["Close"]
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else last
    daily = close.pct_change().dropna()
    vol = float(daily.std() * math.sqrt(ann_days)) if len(daily) > 2 else None
    dd = float((close / close.cummax() - 1).min())
    ret = float(close.iloc[-1] / close.iloc[0] - 1)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Last close", f"{last:,.2f}", f"{(last / prev - 1):.2%}")
    m2.metric(f"Return over {period}", pct(ret))
    m3.metric("Annualised volatility", pct(vol))
    m4.metric("Worst fall (max drawdown)", pct(dd))

    tech, ind, cov = technical_analysis(df)
    st.subheader("Trend score")
    if ind.empty:
        st.info("Need at least 30 price bars for a trend score.")
    else:
        level_box({"Bullish": "success", "Neutral": "info", "Bearish": "error"}.get(tech.verdict, "info"),
                  f"**Trend score {tech.score:.0f}/100: {tech.verdict}** (rule coverage {cov:.0%}). "
                  "This describes the price trend only. It is NOT a buy/sell recommendation.")
        with st.expander("Which rules fired, and why"):
            st.dataframe(reasons_table(tech.reasons), hide_index=True, width="stretch")
        for r in tech.risks:
            st.write(f"⚠️ {r}")
        st.plotly_chart(charts.price_chart(ind), width="stretch", key=f"{key}_chart")

    st.subheader("Backtest: would a simple rule have beaten buy-and-hold?")
    b1, b2 = st.columns([2, 1])
    strat = b1.selectbox("Strategy", list(STRATEGIES), key=f"{key}_strat")
    cost = b2.number_input("Cost per side (%)", 0.0, 5.0, default_cost, 0.05, key=f"{key}_cost") / 100
    st.caption(STRATEGIES[strat])
    try:
        bt = run_backtest(df, strat, cost_pct=cost)
    except ValueError as e:
        st.info(str(e))
    else:
        m = bt.metrics
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Strategy return", pct(m["total_return"]), f"{(m['total_return'] - m['bh_total_return']) * 100:+.1f} pts vs hold")
        t2.metric("Buy & hold return", pct(m["bh_total_return"]))
        t3.metric("Strategy max drawdown", pct(m["max_drawdown"]), f"hold: {pct(m['bh_max_drawdown'])}", delta_color="off")
        t4.metric("Trades / win rate", f"{m['trades']} / {pct(m['win_rate'], 0)}")
        st.plotly_chart(charts.line_chart({"Strategy": bt.equity, "Buy & hold": bt.benchmark}, "Growth of ₹100,000"),
                        width="stretch", key=f"{key}_bt")
        for w in bt.warnings:
            st.write(f"⚠️ {w}")

    with st.expander("Data quality and sources"):
        show_checks(res.checks, res.as_of, res.sources)


gold_tab, crypto_tab = st.tabs(["🥇 Gold", "₿ Crypto"])

with gold_tab:
    asset_panel("gold", "Gold", ["GOLDBEES.NS", "GOLDIETF.NS"], 252, 0.15)
    st.caption("The two ETF tickers above are suggestions: availability on Yahoo is not guaranteed. "
               "Use the custom option for any other symbol.")
    with st.expander("Gold: ways to hold it, and tax notes (verify before acting)", expanded=False):
        st.markdown(
            """
- **Gold ETFs** trade on NSE like stocks (no making charges, small expense ratio, need a demat account).
- **Sovereign Gold Bonds (SGBs)**: pay about 2.5% interest on top of gold-price movement. Redemption at maturity is
  tax-free for individuals *(verify current rules)*. Fresh issuance has been paused for some time, so SGBs are usually
  bought on the exchange, often at a premium or discount to gold.
- **Gold ETF tax:** held more than 12 months is long-term, taxed at 12.5% on gains *(verify the current rate)*;
  otherwise it is taxed at your slab.
- **Physical / digital gold:** extra costs (making charges, GST, spreads). Compare the all-in cost before buying.
- Gold is typically used as a diversifier (5-15% of a portfolio), not a source of high growth.
"""
        )

with crypto_tab:
    st.error("**Very high risk.** Crypto assets are not regulated as securities in India, have no investor-protection "
             "framework, can fall 50-80% in months, and exchanges can fail. Only consider money you can afford to lose entirely.")
    asset_panel("crypto", "Crypto", ["BTC-INR", "ETH-INR"], 365, 0.5)
    with st.expander("Crypto: tax notes (verify with a CA)", expanded=False):
        st.markdown(
            """
- **30% flat tax** on gains from transfer of virtual digital assets, with **no deduction** for expenses other than the cost of acquisition.
- **1% TDS** (Section 194S) on transfers above the thresholds.
- **No set-off:** losses from one crypto asset cannot be set off against gains from another, nor against other income, and cannot be carried forward.
- Rules change often. Confirm the current position with a chartered accountant.
"""
        )
    term("Volatility")
    term("Drawdown")
