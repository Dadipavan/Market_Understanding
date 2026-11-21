import pandas as pd
import streamlit as st

from backtest.engine import STRATEGIES, run_backtest
from datasources.fundamentals import get_fundamentals
from datasources.service import get_prices
from datasources.universe import all_nse_equities, fallback_universe
from datasources.yahoo import DataSourceError
from rules.advisor import DISCLAIMER, investing_report
from ui.charts import line_chart, price_chart
from ui.common import level_box, money, pct, setup, show_checks, term

demo = setup("Stock Investing", "🏢")


# ---------------------------------------------------------------- cached loaders
@st.cache_data(ttl=86400, show_spinner=False)
def load_universe(demo_mode: bool):
    if demo_mode:
        return fallback_universe(), False
    return all_nse_equities()


@st.cache_data(ttl=900, show_spinner=False)
def load_prices(symbol: str, period: str, demo_mode: bool):
    return get_prices(symbol, period, demo=demo_mode)


@st.cache_data(ttl=900, show_spinner=False)
def load_fundamentals(symbol: str, demo_mode: bool):
    try:
        return get_fundamentals(symbol, demo_mode), None
    except DataSourceError as e:
        return None, str(e)
    except Exception as e:  # never let fundamentals break the price analysis
        return None, f"Fundamentals failed: {type(e).__name__}"


def reasons_df(reasons) -> pd.DataFrame:
    return pd.DataFrame([{
        "Rule": r.rule,
        "Result": "➖ n/a" if not r.available else ("✅" if r.passed else "❌"),
        "Points": r.points,
        "Max": r.max_points,
        "Detail": r.detail,
    } for r in reasons])


# ---------------------------------------------------------------- inputs
universe, is_full = load_universe(demo)
names = dict(zip(universe["symbol"], universe["name"]))
symbols = list(universe["symbol"])
default_idx = symbols.index("RELIANCE") if "RELIANCE" in symbols else 0

c1, c2, c3 = st.columns([3, 2, 1])
choice = c1.selectbox("Search any NSE stock (type to filter)", symbols, index=default_idx,
                      format_func=lambda s: f"{s} - {names.get(s, s)}")
custom = c2.text_input("...or type any symbol", placeholder="e.g. IRCTC, 532540.BO").strip().upper()
period = c3.selectbox("History", ["1y", "2y", "5y"], index=1)
if not is_full and not demo:
    st.info("The full NSE stock list could not be loaded, so only NIFTY 50 appears in the dropdown. "
            "Typing any symbol in the box works for every stock (add .BO for BSE-only stocks).")
symbol = custom or choice

with st.spinner(f"Loading {symbol}..."):
    res = load_prices(symbol, period, demo)

if res.df.empty:
    st.error(f"No price data for {symbol}.")
    for c in res.checks:
        st.write(f"❌ **{c.name}**: {c.detail}")
    st.caption("Check the symbol, your network, or whether Yahoo Finance is reachable from where this app runs.")
    st.stop()

info, fund_err = load_fundamentals(symbol, demo)
if fund_err:
    st.warning(f"{fund_err}. Showing a price-trend view only: verify business quality on Screener.in.")
elif not info:
    st.warning("No fundamentals were returned for this symbol. Showing a price-trend view only.")

df = res.df
report = investing_report(symbol, df, info, verified=res.verified)

# ---------------------------------------------------------------- header
last = float(df["Close"].iloc[-1])
prev = float(df["Close"].iloc[-2]) if len(df) > 1 else last
yr = df.tail(252)
title = (info or {}).get("name") or names.get(symbol, symbol)
st.subheader(f"{title} ({symbol})")
sec = (info or {}).get("sector")
if sec:
    st.caption(f"{sec} | {(info or {}).get('industry') or ''}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Last close", money(last), f"{(last / prev - 1):+.2%}")
m2.metric("52-week high", money(float(yr["High"].max())))
m3.metric("52-week low", money(float(yr["Low"].min())))
mc = (info or {}).get("market_cap")
m4.metric("Market cap", f"₹{mc / 1e7:,.0f} Cr" if mc else "n/a")

tab_adv, tab_chart, tab_fund, tab_bt, tab_dq = st.tabs(
    ["Advisor report", "Chart", "Fundamentals", "Backtest", "Data quality"])

# ---------------------------------------------------------------- advisor
with tab_adv:
    level_box(report.level, f"**{report.verdict}**")
    a, b, c = st.columns(3)
    a.metric("Combined score", f"{report.score:.0f}/100")
    b.metric("Technical score", f"{report.technical.score:.0f}/100", f"{report.tech_coverage:.0%} of rules had data", delta_color="off")
    if report.fundamental is not None:
        c.metric("Fundamental score", f"{report.fundamental.score:.0f}/100", f"{report.fund_coverage:.0%} of rules had data", delta_color="off")
    else:
        c.metric("Fundamental score", "n/a", "no usable fundamentals", delta_color="off")

    st.markdown("#### Why")
    st.write(report.summary)

    st.markdown("#### Levels to watch")
    z1, z2 = st.columns(2)
    if report.entry_zone:
        z1.metric("Accumulation zone", f"{money(report.entry_zone[0])} - {money(report.entry_zone[1])}",
                  help="Between nearby support/200-day average and the 50-day average (or price if lower).")
    if report.invalidation:
        z2.metric("Thesis-invalidation level", money(report.invalidation),
                  help="A close below this breaks the long-term uptrend structure: re-evaluate the holding.")

    if report.risks:
        st.markdown("#### Risks and caveats")
        for r in report.risks:
            st.write(f"- {r}")

    with st.expander("Technical rules (what fired and why)", expanded=True):
        st.dataframe(reasons_df(report.technical.reasons), hide_index=True, width="stretch")
    if report.fundamental is not None:
        with st.expander("Fundamental rules (what fired and why)", expanded=True):
            st.dataframe(reasons_df(report.fundamental.reasons), hide_index=True, width="stretch")
    term("RSI")
    term("P/E ratio")
    term("ROE / ROCE")
    st.caption(DISCLAIMER)

# ---------------------------------------------------------------- chart
with tab_chart:
    ind = report.indicators
    if ind is None or ind.empty:
        st.info("Not enough price history to draw indicators.")
    else:
        t1, t2, t3, t4 = st.columns(4)
        show_ema = t1.checkbox("EMA 50/200", True)
        show_bb = t2.checkbox("Bollinger bands", False)
        show_rsi = t3.checkbox("RSI", True)
        show_macd = t4.checkbox("MACD", True)
        levels = {}
        if report.entry_zone:
            levels["Zone low"], levels["Zone high"] = report.entry_zone
        if report.invalidation:
            levels["Invalidation"] = report.invalidation
        st.plotly_chart(price_chart(ind, show_ema, show_bb, show_rsi, show_macd, levels), width="stretch")
        st.caption("Dashed lines: accumulation zone and thesis-invalidation level from the advisor.")

# ---------------------------------------------------------------- fundamentals
with tab_fund:
    if not info:
        st.info("Fundamentals are not available for this symbol right now.")
    else:
        grid = [
            ("P/E", f"{info['pe']:.1f}" if info.get("pe") is not None else "n/a"),
            ("P/B", f"{info['pb']:.2f}" if info.get("pb") is not None else "n/a"),
            ("ROE", pct(info.get("roe"))),
            ("Net margin", pct(info.get("profit_margin"))),
            ("Operating margin", pct(info.get("operating_margin"))),
            ("Revenue growth", pct(info.get("revenue_growth"))),
            ("Earnings growth", pct(info.get("earnings_growth"))),
            ("Debt / equity", f"{info['debt_to_equity']:.2f}" if info.get("debt_to_equity") is not None else "n/a"),
            ("Current ratio", f"{info['current_ratio']:.2f}" if info.get("current_ratio") is not None else "n/a"),
            ("Insider holding", pct(info.get("promoter_holding"))),
            ("Dividend yield", pct(info.get("dividend_yield"), 2)),
            ("Beta", f"{info['beta']:.2f}" if info.get("beta") is not None else "n/a"),
        ]
        for i in range(0, len(grid), 4):
            cols = st.columns(4)
            for col, (k, v) in zip(cols, grid[i:i + 4]):
                col.metric(k, v)
        st.caption(f"Source: {info.get('source', 'n/a')}. Free fundamentals for Indian companies are often stale or missing: cross-check on Screener.in.")
        if report.fundamental is not None:
            st.dataframe(reasons_df(report.fundamental.reasons), hide_index=True, width="stretch")
        term("Debt / equity")
        term("Promoter holding & pledging")

# ---------------------------------------------------------------- backtest
with tab_bt:
    st.write("Test a simple rule on this stock's history, with trading costs, against just buying and holding.")
    b1, b2 = st.columns([2, 1])
    strat = b1.selectbox("Strategy", list(STRATEGIES))
    cost = b2.number_input("Cost per trade side (%)", 0.0, 2.0, 0.15, 0.05,
                           help="Brokerage + STT + charges + slippage, applied on every buy and every sell.") / 100
    st.caption(STRATEGIES[strat])
    try:
        bt = run_backtest(df, strat, cost_pct=cost)
    except ValueError as e:
        st.warning(str(e))
        bt = None
    if bt is not None:
        m = bt.metrics
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Strategy total return", pct(m["total_return"]), f"vs buy&hold {pct(m['bh_total_return'])}", delta_color="off")
        k2.metric("CAGR", pct(m["cagr"]), f"buy&hold {pct(m['bh_cagr'])}", delta_color="off")
        k3.metric("Max drawdown", pct(m["max_drawdown"]), f"buy&hold {pct(m['bh_max_drawdown'])}", delta_color="off")
        k4.metric("Sharpe", f"{m['sharpe']:.2f}", f"buy&hold {m['bh_sharpe']:.2f}", delta_color="off")
        k5, k6, k7 = st.columns(3)
        k5.metric("Trades", m["trades"])
        k6.metric("Win rate", pct(m["win_rate"], 0))
        k7.metric("Time invested", pct(m["exposure"], 0))
        st.plotly_chart(line_chart({"Strategy": bt.equity, "Buy & hold": bt.benchmark}, "Growth of ₹1,00,000"), width="stretch")
        for w in bt.warnings:
            st.warning(w)
        if len(bt.trades):
            t = bt.trades.copy()
            t["return"] = (t["return"] * 100).round(2)
            st.dataframe(t.rename(columns={"return": "return %"}), hide_index=True, width="stretch")

# ---------------------------------------------------------------- data quality
with tab_dq:
    show_checks(res.checks, res.as_of, res.sources)
    if res.demo:
        st.error("These are synthetic demo prices, not real market data.")
