import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from datasources.service import get_prices
from portfolio.ledger import Ledger
from ui.common import BLUE, money, setup

demo = setup("Paper Portfolio", "📒")
st.info("Your paper portfolio lives only in this browser session. It is **never stored on the server**: "
        "download the JSON backup below to keep it, and import it next time.")


@st.cache_data(ttl=900, show_spinner=False)
def _last_close(symbol: str, is_demo: bool):
    r = get_prices(symbol, "1mo", demo=is_demo, cross_verify=False)
    if r.df.empty:
        return None
    return float(r.df["Close"].iloc[-1])


if "ledger" not in st.session_state:
    st.session_state["ledger"] = Ledger()
led: Ledger = st.session_state["ledger"]

# ------------------------------------------------------------------ starting cash
if not led.trades:
    led.starting_cash = st.number_input("Starting virtual cash (₹)", min_value=1000.0, value=float(led.starting_cash), step=50000.0,
                                        help="Can only be changed before your first trade.")
else:
    st.caption(f"Starting cash: {money(led.starting_cash)} (locked after the first trade; reset to change).")

# ------------------------------------------------------------------ prices for held symbols
_, hold = led.state()
prices: dict[str, float] = {}
failed: list[str] = []
for sym in hold:
    px = _last_close(sym, demo)
    if px is None:
        failed.append(sym)
    else:
        prices[sym] = px
if failed:
    st.warning(f"Could not fetch current prices for {', '.join(failed)}: using your average cost instead, so P&L for these shows as 0.")

# ------------------------------------------------------------------ summary
s = led.summary(prices)
a, b, c, d = st.columns(4)
a.metric("Equity (cash + holdings)", money(s["equity"]), f"{s['total_return_pct']:+.2f}%")
b.metric("Cash", money(s["cash"]))
c.metric("Holdings value", money(s["holdings_value"]))
d.metric("Realised P&L", money(s["realised_pnl"]))
e, f, g, h = st.columns(4)
e.metric("Fees paid", money(s["fees_paid"]))
f.metric("Closed trades", s["closed_trades"])
g.metric("Win rate", f"{s['win_rate']:.0%}" if s["closed_trades"] else "n/a")
h.metric("Expectancy / trade", money(s["expectancy"]) if s["closed_trades"] else "n/a",
         help="Average realised profit per closed trade after fees. Positive means your process is working.")
if s["concentration_pct"] > 25:
    st.warning(f"Concentration: your largest holding is {s['concentration_pct']:.1f}% of equity. Above ~25% in one stock is risky.")
if s["closed_trades"]:
    st.caption(f"Average win {money(s['avg_win'])} | average loss {money(s['avg_loss'])}")

# ------------------------------------------------------------------ holdings
st.subheader("Holdings")
ht = led.holdings_table(prices)
if ht.empty:
    st.info("No open positions yet. Add a trade below or from the Trading page.")
else:
    st.dataframe(ht, hide_index=True, width="stretch")
    labels = list(ht["symbol"]) + ["Cash"]
    values = [v if v == v and v is not None else 0 for v in ht["value"]] + [s["cash"]]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=BLUE, marker_line_width=0))
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="Value (₹)", showlegend=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)")
    st.plotly_chart(fig, width="stretch")

# ------------------------------------------------------------------ manual trade
st.subheader("Add a trade")
with st.form("trade_form", clear_on_submit=False):
    f1, f2, f3, f4 = st.columns(4)
    sym = f1.text_input("Symbol", value="RELIANCE").strip().upper()
    side = f2.selectbox("Side", ["buy", "sell"])
    qty = f3.number_input("Quantity", min_value=1, value=10, step=1)
    price = f4.number_input("Price (₹)", min_value=0.01, value=100.0, step=1.0)
    g1, g2, g3, g4 = st.columns(4)
    day = g1.date_input("Date", value=dt.date.today())
    kind = g2.selectbox("Type", ["delivery", "intraday"])
    stop = g3.number_input("Stop-loss (optional, 0 = none)", min_value=0.0, value=0.0, step=1.0)
    target = g4.number_input("Target (optional, 0 = none)", min_value=0.0, value=0.0, step=1.0)
    note = st.text_input("Journal note (why this trade? how did you feel?)")
    submitted = st.form_submit_button("Add trade")
if submitted:
    if not sym:
        st.error("Enter a symbol.")
    else:
        try:
            t = led.add_trade(day, sym, side, int(qty), float(price), kind, stop=stop or None, target=target or None, note=note)
            st.success(f"{side.title()} {t['qty']} {t['symbol']} at {money(t['price'])} recorded (fees {money(t['fees'])}).")
            st.rerun()
        except ValueError as ex:
            st.error(f"Trade rejected: {ex}")

# ------------------------------------------------------------------ journal
st.subheader("Trade journal")
tdf = led.trades_df()
if tdf.empty:
    st.caption("Your trades will appear here. Review them monthly: what worked, what you repeated, where you broke your own rules.")
else:
    st.dataframe(tdf, hide_index=True, width="stretch")

# ------------------------------------------------------------------ backup / reset
st.subheader("Backup and restore")
b1, b2 = st.columns(2)
with b1:
    st.download_button("⬇️ Download portfolio (JSON)", data=led.to_json(), file_name="paper_portfolio.json", mime="application/json")
with b2:
    up = st.file_uploader("Import a saved portfolio (JSON)", type=["json"])
    if up is not None and st.button("Import file"):
        try:
            st.session_state["ledger"] = Ledger.from_json(up.getvalue().decode("utf-8"))
            st.success("Portfolio imported.")
            st.rerun()
        except (ValueError, KeyError, TypeError) as ex:
            st.error(f"Could not import: {ex}")

with st.expander("Reset portfolio"):
    sure = st.checkbox("I understand this deletes all paper trades in this session")
    if st.button("Reset", disabled=not sure):
        st.session_state["ledger"] = Ledger()
        st.rerun()
