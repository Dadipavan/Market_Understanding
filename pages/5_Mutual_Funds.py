import pandas as pd
import requests
import streamlit as st

from funds.amfi import all_schemes, demo_nav, demo_schemes, nav_history
from funds.analytics import (expense_drag, fund_analysis, fund_metrics, rolling_returns, sip_backtest,
                             sip_future_value)
from ui.charts import line_chart
from ui.common import level_box, money, pct, setup, term

demo = setup("Mutual Funds", "🏦")
st.caption("Fund data: official AMFI NAV file (scheme list) and mfapi.in (free community API, unofficial) for NAV history.")


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_schemes(demo_mode: bool) -> pd.DataFrame:
    return demo_schemes() if demo_mode else all_schemes()


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def load_nav(code: str, demo_mode: bool) -> pd.Series:
    return demo_nav(code) if demo_mode else nav_history(code)


def friendly(e: Exception) -> str:
    if isinstance(e, requests.RequestException):
        return f"Could not reach the fund data source ({type(e).__name__}). Check your network or try again later."
    return f"Fund data problem: {e}"


try:
    with st.spinner("Loading scheme list..."):
        schemes = load_schemes(demo)
except (requests.RequestException, ValueError) as e:
    st.error(friendly(e))
    st.stop()

# ----------------------------------------------------------------------------- search & pick
c1, c2 = st.columns([3, 1])
query = c1.text_input("Search schemes (e.g. 'parag flexi', 'nifty 50 index')").strip().lower()
direct_growth = c2.toggle("Direct + Growth only", value=True, help="Direct plans have lower costs; Growth plans reinvest returns.")
pool = schemes
if direct_growth:
    n = pool["name"].str.lower()
    pool = pool[n.str.contains("direct") & n.str.contains("growth") & ~n.str.contains("idcw|dividend|payout")]
for w in query.split():
    pool = pool[pool["name"].str.lower().str.contains(w, regex=False)]
pool = pool.head(300)
if pool.empty:
    st.info("No schemes match. Try fewer words, or switch off 'Direct + Growth only'.")
    st.stop()
labels = dict(zip(pool["code"], pool["name"]))
code = st.selectbox("Scheme", list(labels), format_func=lambda c: f"{labels[c]} ({c})")

try:
    with st.spinner("Loading NAV history..."):
        nav = load_nav(code, demo)
except (requests.RequestException, ValueError) as e:
    st.error(friendly(e))
    st.stop()
nav = nav.dropna().sort_index()
if len(nav) < 30:
    st.warning("Too little NAV history to analyse this scheme.")
    st.stop()

st.caption(f"Latest NAV ₹{nav.iloc[-1]:,.4f} on {nav.index[-1]:%Y-%m-%d} | {len(nav):,} data points since {nav.index[0]:%Y-%m-%d}")

# ----------------------------------------------------------------------------- analysis
m = fund_metrics(nav)
analysis, coverage = fund_analysis(m)
level = {"Strong": "success", "Average": "warning", "Weak": "error"}.get(analysis.verdict, "info")
level_box(level, f"### Fund score: {analysis.verdict} ({analysis.score:.0f}/100) | rule coverage {coverage:.0%}")

k = st.columns(6)
k[0].metric("1-yr CAGR", pct(m["cagr_1y"]))
k[1].metric("3-yr CAGR", pct(m["cagr_3y"]))
k[2].metric("5-yr CAGR", pct(m["cagr_5y"]))
k[3].metric("Volatility (ann.)", pct(m["volatility"]))
k[4].metric("Max drawdown", pct(m["max_drawdown"]))
k[5].metric("Sharpe-style", "n/a" if m["sharpe"] is None else f"{m['sharpe']:.2f}")

rt = pd.DataFrame([{"Rule": r.rule, "Result": ("✅ passed" if r.passed else "❌ not met") if r.available else "➖ no data",
                    "Points": r.points if r.available else None, "Max": r.max_points, "Why": r.detail} for r in analysis.reasons])
st.dataframe(rt, width="stretch", hide_index=True)
for r in analysis.risks:
    st.write(f"⚠️ {r}")

window = st.radio("Chart window", ["1Y", "3Y", "5Y", "Max"], index=3, horizontal=True)
yrs = {"1Y": 1, "3Y": 3, "5Y": 5}.get(window)
nav_w = nav[nav.index >= nav.index[-1] - pd.DateOffset(years=yrs)] if yrs else nav

st.plotly_chart(line_chart({"NAV": nav_w}, "NAV (₹)"), width="stretch")
cc1, cc2 = st.columns(2)
with cc1:
    rr = rolling_returns(nav, 1)
    rr = rr[rr.index.isin(nav_w.index)]
    if rr.empty:
        st.info("Not enough history for rolling 1-year returns.")
    else:
        st.plotly_chart(line_chart({"Rolling 1-yr return": rr}, "Rolling 1-year return", 320, ".0%"), width="stretch")
with cc2:
    dd = nav_w / nav_w.cummax() - 1
    st.plotly_chart(line_chart({"Drawdown": dd}, "Drawdown from previous peak", 320, ".0%"), width="stretch")

# ----------------------------------------------------------------------------- compare
st.subheader("Compare funds")
others = [c for c in labels if c != code]
picks = st.multiselect("Compare with (up to 2 more)", others, max_selections=2,
                       format_func=lambda c: f"{labels[c]} ({c})")
if picks:
    series = {labels[code][:40]: nav}
    for pc in picks:
        try:
            series[labels[pc][:40]] = load_nav(pc, demo).dropna().sort_index()
        except (requests.RequestException, ValueError) as e:
            st.warning(f"{labels[pc]}: {friendly(e)}")
    start = max(s.index[0] for s in series.values())
    norm = {n: s[s.index >= start] / s[s.index >= start].iloc[0] * 100 for n, s in series.items() if (s.index >= start).any()}
    st.caption(f"Normalised to 100 at {start:%Y-%m-%d}, the start of the shortest history.")
    st.plotly_chart(line_chart(norm, "Growth of 100"), width="stretch")
    rows = []
    for n, s in series.items():
        mm = fund_metrics(s)
        rows.append({"Fund": n, "1y": pct(mm["cagr_1y"]), "3y": pct(mm["cagr_3y"]), "5y": pct(mm["cagr_5y"]),
                     "Volatility": pct(mm["volatility"]), "Max drawdown": pct(mm["max_drawdown"]),
                     "Score": fund_analysis(mm)[0].score})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

# ----------------------------------------------------------------------------- SIP
st.subheader("SIP planner")
s1, s2 = st.columns(2)
with s1:
    st.markdown("**What-if calculator**")
    monthly = st.number_input("Monthly SIP (₹)", 500, 10_000_000, 10_000, 500)
    years = st.slider("Years", 1, 40, 10)
    ret = st.slider("Expected annual return (%)", 1.0, 25.0, 12.0, 0.5)
    fv = sip_future_value(monthly, years, ret / 100)
    st.metric("Future value", money(fv["future_value"]))
    st.caption(f"Invested {money(fv['invested'])} | estimated gain {money(fv['gain'])}. An assumption, not a promise.")
with s2:
    st.markdown("**Backtest on this fund's real NAV**")
    max_y = max(1, int(m["history_years"]))
    by = st.slider("Look-back (years)", 1, max_y, min(3, max_y)) if max_y > 1 else 1
    res = sip_backtest(nav, monthly, by)
    if res is None:
        st.info("Not enough history for this look-back.")
    else:
        st.metric("Value today", money(res["value"]))
        st.caption(f"{res['installments']} instalments, invested {money(res['invested'])}, gain {money(res['gain'])}")
        st.metric("XIRR (annualised)", pct(res["xirr"]) if res["xirr"] is not None else "n/a")

st.subheader("Expense-ratio drag")
e1, e2, e3, e4 = st.columns(4)
g = e1.number_input("Gross return (%)", 1.0, 30.0, 12.0, 0.5)
lo = e2.number_input("Low-cost expense ratio (%)", 0.0, 3.0, 0.5, 0.1)
hi = e3.number_input("High-cost expense ratio (%)", 0.0, 3.5, 1.5, 0.1)
ey = e4.number_input("Years", 1, 40, 20)
if hi < lo:
    st.error("High-cost ratio must be at least the low-cost ratio.")
else:
    d = expense_drag(monthly, ey, g / 100, lo / 100, hi / 100)
    st.write(f"Over {ey} years a ₹{monthly:,.0f} monthly SIP grows to **{money(d['low_cost_value'])}** at {lo}% cost vs "
             f"**{money(d['high_cost_value'])}** at {hi}%: a difference of **{money(d['difference'])}**.")

with st.expander("ℹ️ Learn: fund terms"):
    for t in ("NAV", "SIP", "Expense ratio", "XIRR"):
        term(t)
