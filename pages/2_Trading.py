import datetime as dt

import pandas as pd
import streamlit as st

from datasources.service import get_prices
from datasources.universe import all_nse_equities, fallback_universe
from indicators.technical import add_indicators
from portfolio.ledger import Ledger
from risk.costs import capital_gains_tax, round_trip
from rules.advisor import trading_setup
from ui.charts import price_chart
from ui.common import level_box, money, setup, show_checks, term

demo = setup("Trading", "⚡")
st.caption("Short-term setups with a stop-loss, targets and risk-based position size. Long (buy) side only. Paper trading: no real orders are placed.")


@st.cache_data(ttl=900, show_spinner=False)
def _prices(symbol: str, period: str, is_demo: bool):
    return get_prices(symbol, period, demo=is_demo)


@st.cache_data(ttl=86400, show_spinner=False)
def _universe(is_demo: bool):
    if is_demo:
        return fallback_universe(), False
    return all_nse_equities()


def _ledger() -> Ledger:
    if "ledger" not in st.session_state:
        st.session_state["ledger"] = Ledger()
    return st.session_state["ledger"]


# ------------------------------------------------------------------ inputs
uni, full = _universe(demo)
c1, c2 = st.columns([1, 2])
typed = c1.text_input("NSE symbol", value="RELIANCE", help="Any NSE-listed stock, e.g. IRCTC, TATAMOTORS. Use 532540.BO style for BSE-only stocks.").strip().upper()
names = dict(zip(uni["symbol"], uni["name"]))
picked = c2.selectbox(
    "...or pick from the list" + ("" if full else " (NIFTY 50 only: full NSE list unavailable right now)"),
    [""] + list(uni["symbol"]),
    format_func=lambda s: "(use the typed symbol)" if not s else f"{s} - {names.get(s, '')}",
)
symbol = picked or typed

i1, i2, i3, i4, i5 = st.columns(5)
capital = i1.number_input("Trading capital (₹)", min_value=1000.0, value=500000.0, step=10000.0)
risk_pct = i2.number_input("Risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1,
                           help="Maximum % of capital you will lose if the stop-loss is hit. 1-2% is standard.")
kind = i3.selectbox("Trade type", ["delivery", "intraday"])
max_pos = i4.number_input("Max position (% of capital)", min_value=1.0, max_value=100.0, value=25.0, step=5.0,
                          help="Caps any single position so one stock cannot dominate your capital (no leverage).")
period = i5.selectbox("History", ["1y", "2y"], help="At least ~1 year is needed for the 200-day average.")

if not symbol:
    st.info("Enter an NSE symbol to begin.")
    st.stop()

with st.spinner(f"Fetching {symbol}..."):
    res = _prices(symbol, period, demo)

if res.df.empty:
    st.error(f"No data for {symbol}.")
    for c in res.checks:
        st.write(f"❌ **{c.name}**: {c.detail}")
    st.caption("Check the symbol, your network/VPN, or whether this data source is reachable from here.")
    st.stop()

setup_ = trading_setup(symbol, res.df, capital, risk_pct, kind, max_pos)
if setup_ is None:
    st.warning("Not enough price history to build a setup (need at least ~30 bars).")
    st.stop()

if not res.verified and not demo:
    st.warning("Data failed one or more quality checks. Verify the price on NSE or your broker before trading.")

# ------------------------------------------------------------------ verdict
st.subheader(f"{symbol}: setup grade {setup_.grade}")
level_box(setup_.level, f"**Grade {setup_.grade}** (technical score {setup_.score:.0f}/100). "
          + {"A": "Most rules agree: a full-size setup if you accept the stop.",
             "B": "Mixed signals: consider half size or wait for confirmation.",
             "No trade": "Rules do not agree: no trade is a valid decision."}[setup_.grade])

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Entry (last close)", money(setup_.entry))
m2.metric("Stop-loss", money(setup_.stop), f"{(setup_.stop / setup_.entry - 1):.2%}")
m3.metric("Target 1 (2R)", money(setup_.target1), f"{(setup_.target1 / setup_.entry - 1):+.2%}")
m4.metric("Target 2 (3R)", money(setup_.target2), f"{(setup_.target2 / setup_.entry - 1):+.2%}")
m5.metric("Risk-reward to T1", f"1 : {setup_.risk_reward_t1:.1f}")

for n in setup_.notes:
    st.write(f"• {n}")

# ------------------------------------------------------------------ sizing + costs
st.subheader("Position size and costs")
sz = setup_.sizing
s1, s2 = st.columns(2)
with s1:
    st.dataframe(pd.DataFrame({
        "Item": ["Quantity (shares)", "Capital used", "Capital used (% of capital)", "Risk if stop hits", "Risk per share"],
        "Value": [f"{sz['qty']:,}", money(sz["capital_used"]), f"{sz['capital_used'] / capital:.1%}",
                  money(sz["risk_amount"]), money(sz["per_share_risk"])],
    }), hide_index=True, width="stretch")
    if sz.get("note"):
        st.caption(sz["note"])
with s2:
    if setup_.costs_t1:
        ct = setup_.costs_t1
        st.dataframe(pd.DataFrame({
            "If target 1 is hit": ["Gross profit", "Charges (buy + sell)", "Net profit", "Move needed just to break even"],
            "Value": [money(ct["gross_pnl"]), money(ct["costs"]), money(ct["net_pnl"]), f"{ct['breakeven_move_pct']:.2f}%"],
        }), hide_index=True, width="stretch")
        st.caption("Charges are approximate (STT, exchange fees, GST, stamp duty, DP). Check your broker's contract note.")
    else:
        st.info("No position size at this stop distance, so no cost estimate.")

# ------------------------------------------------------------------ chart
st.subheader("Chart with trade levels")
ind = add_indicators(res.df)
levels = {"Entry": setup_.entry, "Stop": setup_.stop, "Target 1": setup_.target1, "Target 2": setup_.target2}
if setup_.nearest_resistance:
    levels["Resistance"] = setup_.nearest_resistance
st.plotly_chart(price_chart(ind.tail(180), levels=levels), width="stretch")

# ------------------------------------------------------------------ why
with st.expander("Why this grade? (technical rules)", expanded=False):
    rows = [{"Rule": r.rule, "Result": "✅" if r.passed else ("➖ n/a" if not r.available else "❌"),
             "Points": f"{r.points:.0f}/{r.max_points:.0f}", "Detail": r.detail} for r in setup_.technical.reasons]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    for r in setup_.technical.risks:
        st.write(f"⚠️ {r}")

# ------------------------------------------------------------------ tax
with st.expander("Tax estimate (listed equity, approximate)"):
    t1, t2, t3 = st.columns(3)
    sell_px = t1.number_input("Expected sell price (₹)", min_value=0.01, value=float(setup_.target1))
    t_qty = t2.number_input("Quantity", min_value=1, value=max(int(sz["qty"]), 1), step=1)
    hold_days = t3.number_input("Holding period (days)", min_value=0, value=5, step=1)
    gross = (sell_px - setup_.entry) * t_qty
    rt = round_trip(setup_.entry, sell_px, int(t_qty), kind)
    tax = capital_gains_tax(rt["net_pnl"], int(hold_days))
    st.write(f"Net profit before tax: **{money(rt['net_pnl'])}** (gross {money(gross)} minus charges {money(rt['costs'])}).")
    st.write(f"Tax type: **{tax['type']}**, estimated tax **{money(tax['tax'])}** (incl. 4% cess). "
             f"Take-home after tax: **{money(rt['net_pnl'] - tax['tax'])}**.")
    st.caption("Uses 20% STCG (up to 12 months) and 12.5% LTCG above ₹1.25 lakh/yr (Budget 2024). Intraday gains are taxed as business income at your slab: "
               "this estimate does not apply. Rules change: confirm with a tax professional.")

# ------------------------------------------------------------------ add to paper portfolio
st.subheader("Practise it: add to paper portfolio")
note = st.text_input("Journal note (why are you taking this trade?)", value=f"Grade {setup_.grade} setup, score {setup_.score:.0f}")
if st.button("➕ Add this trade to paper portfolio", disabled=sz["qty"] <= 0):
    try:
        t = _ledger().add_trade(dt.date.today(), symbol, "buy", int(sz["qty"]), float(setup_.entry), kind,
                                stop=float(setup_.stop), target=float(setup_.target1), note=note)
        st.success(f"Paper trade added: bought {t['qty']} {t['symbol']} at {money(t['price'])} (fees {money(t['fees'])}). See the Paper Portfolio page.")
    except ValueError as e:
        st.error(f"Could not add trade: {e}")
if sz["qty"] <= 0:
    st.caption("Add is disabled because the position size is zero.")

# ------------------------------------------------------------------ learn
st.divider()
st.subheader("Learn the terms")
for t in ("Stop-loss", "Position sizing", "Risk-reward (R)", "ATR"):
    term(t)

with st.expander("Data quality and sources"):
    show_checks(res.checks, res.as_of, res.sources)
