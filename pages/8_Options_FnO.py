import numpy as np
import pandas as pd
import streamlit as st

from derivatives.options import PRESETS, Leg, analyse_payoff, bs_price, greeks, implied_vol, preset
from ui import charts
from ui.common import setup, term

setup("Options (F&O)", "🧮")
st.error("**Extreme risk.** SEBI studies found that roughly **9 in 10 individual F&O traders lost money**, and losses "
         "were larger after costs. This page is for **education and paper analysis only**: there is no live option chain, "
         "no order placement, and all premiums shown are model estimates (Black-Scholes), not market quotes.")

price_tab, strat_tab, learn_tab = st.tabs(["Pricing & Greeks", "Strategy builder", "Learn"])

with price_tab:
    st.subheader("Black-Scholes price and Greeks")
    c1, c2, c3, c4, c5 = st.columns(5)
    spot = c1.number_input("Spot price (₹)", 1.0, 10_000_000.0, 24000.0, 50.0, key="p_spot")
    strike = c2.number_input("Strike (₹)", 1.0, 10_000_000.0, 24000.0, 50.0, key="p_strike")
    days = c3.number_input("Days to expiry", 1, 730, 30, key="p_days")
    rate = c4.number_input("Risk-free rate (%)", 0.0, 20.0, 6.5, 0.1, key="p_rate") / 100
    vol = c5.number_input("Volatility (% a year)", 1.0, 300.0, 15.0, 0.5, key="p_vol") / 100
    T = days / 365
    rows, prices = [], {}
    for kind in ("call", "put"):
        p = bs_price(kind, spot, strike, T, rate, vol)
        g = greeks(kind, spot, strike, T, rate, vol)
        prices[kind] = p
        rows.append({"Option": kind.capitalize(), "Price (₹)": round(p, 2), "Delta": round(g["delta"], 4),
                     "Gamma": round(g["gamma"], 6), "Theta / day (₹)": round(g["theta_per_day"], 3),
                     "Vega per 1% vol (₹)": round(g["vega_per_1pct"], 3), "Rho per 1% rate (₹)": round(g["rho_per_1pct"], 3)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    moneyness = "at the money" if abs(spot - strike) / spot < 0.005 else ("call in the money, put out of the money" if spot > strike else "put in the money, call out of the money")
    st.caption(f"Spot vs strike: {moneyness}. Theta is what a long option loses per day just from time passing.")

    st.subheader("Implied volatility from a quoted premium")
    i1, i2 = st.columns(2)
    kind = i1.selectbox("Option type", ["call", "put"], key="iv_kind")
    quote = i2.number_input("Premium you see in the market (₹)", 0.0, 10_000_000.0, round(prices[kind], 2), 1.0, key="iv_quote")
    iv = implied_vol(kind, quote, spot, strike, T, rate)
    if iv is None:
        st.warning("No volatility reproduces that premium (it is below intrinsic value, or too high). Re-check the inputs.")
    else:
        st.metric("Implied volatility", f"{iv * 100:.2f}%")
        st.caption("Implied volatility is the market's expectation of future movement baked into the price. "
                   "Buying options when it is very high is usually expensive.")
    term("Delta, gamma, theta, vega")
    term("Premium, strike, expiry")

with strat_tab:
    st.subheader("Build a strategy and see profit/loss at expiry")
    a1, a2, a3, a4 = st.columns(4)
    name = a1.selectbox("Strategy", PRESETS, key="s_name")
    spot = a2.number_input("Spot (₹)", 1.0, 10_000_000.0, 24000.0, 50.0, key="s_spot")
    step = a3.number_input("Strike step (₹)", 1.0, 10_000.0, 100.0, 5.0, key="s_step")
    lot = a4.number_input("Lot size (check NSE for the current value)", 1, 100_000, 75, key="s_lot")
    b1, b2, b3, b4 = st.columns(4)
    lots = b1.number_input("Lots", 1, 1000, 1, key="s_lots")
    days = b2.number_input("Days to expiry", 1, 365, 30, key="s_days")
    vol = b3.number_input("Volatility (% a year)", 1.0, 300.0, 15.0, 0.5, key="s_vol") / 100
    rate = b4.number_input("Risk-free rate (%)", 0.0, 20.0, 6.5, 0.1, key="s_rate") / 100
    units = int(lot * lots)
    T = days / 365

    def premium_fn(kind: str, k: float) -> float:
        return round(bs_price(kind, spot, k, T, rate, vol), 2)

    legs = preset(name, spot, step, premium_fn, units)
    base = pd.DataFrame([{"kind": l.kind, "strike": l.strike, "premium": l.premium, "qty": l.qty} for l in legs])
    st.caption("Legs (you can edit premiums, strikes or quantities; positive qty = long/bought, negative = short/sold):")
    key = f"legs_{name}_{spot}_{step}_{vol}_{days}_{units}_{rate}"
    edited = st.data_editor(
        base, key=key, num_rows="dynamic", hide_index=True, width="stretch",
        column_config={"kind": st.column_config.SelectboxColumn("Type", options=["call", "put", "stock"], required=True),
                       "strike": st.column_config.NumberColumn("Strike / entry (₹)", format="%.2f"),
                       "premium": st.column_config.NumberColumn("Premium (₹/unit)", format="%.2f"),
                       "qty": st.column_config.NumberColumn("Qty (units)", step=1)})
    clean = edited.dropna(subset=["kind", "strike", "qty"]).copy()
    clean["premium"] = clean["premium"].fillna(0.0)
    clean = clean[clean["kind"].isin(["call", "put", "stock"]) & (clean["qty"] != 0) & (clean["strike"] > 0)]
    if clean.empty:
        st.info("Add at least one valid leg.")
    else:
        my_legs = [Leg(r.kind, float(r.strike), float(r.premium), int(r.qty)) for r in clean.itertuples()]
        res = analyse_payoff(my_legs, spot)
        net = res["net_premium"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Net premium", f"₹{abs(net):,.0f} {'credit' if net > 0 else 'debit' if net < 0 else ''}".strip())
        m2.metric("Max profit", "Unlimited*" if res["max_profit"] is None else f"₹{res['max_profit']:,.0f}")
        m3.metric("Max loss", "Unlimited*" if res["max_loss"] is None else f"₹{res['max_loss']:,.0f}")
        m4.metric("Breakeven(s)", ", ".join(f"{b:,.0f}" for b in res["breakevens"]) or "none in range")
        st.plotly_chart(charts.payoff_chart(res["prices"], res["pnl"], spot, res["breakevens"]), width="stretch", key="payoff")
        st.caption("*Beyond the plotted range (spot ±40%). For long stock the loss is bounded by a zero price but is still very large.")

        net_delta = net_theta = net_vega = 0.0
        for l in my_legs:
            if l.kind == "stock":
                net_delta += l.qty
            else:
                g = greeks(l.kind, spot, l.strike, T, rate, vol)
                net_delta += g["delta"] * l.qty
                net_theta += g["theta_per_day"] * l.qty
                net_vega += g["vega_per_1pct"] * l.qty
        g1, g2, g3 = st.columns(3)
        g1.metric("Net delta (units of underlying)", f"{net_delta:,.1f}")
        g2.metric("Net theta per day (₹)", f"{net_theta:,.0f}")
        g3.metric("Net vega per 1% vol (₹)", f"{net_vega:,.0f}")

        short_opts = [l for l in my_legs if l.kind in ("call", "put") and l.qty < 0]
        if short_opts:
            st.warning("**Short option legs:** sellers must post margin (often several lakh rupees), can be forced to square off, "
                       "and naked short calls/puts carry very large or unlimited loss. Margin is not modelled here: check your broker's margin calculator.")
        if any(l.kind in ("call", "put") for l in my_legs) and days <= 7:
            st.info("Near expiry, small price moves swing option values heavily and time decay is fastest.")
    st.caption("Payoff is at expiry only; before expiry, value also depends on volatility and time left. Costs (brokerage, STT, taxes) are not included.")

with learn_tab:
    st.subheader("Reading the strategies")
    for title, text in [
        ("Long call / long put", "Pay a premium for the right to buy/sell. Maximum loss is the premium; profit needs a big, fast move because time decay works against you."),
        ("Covered call", "Own the stock and sell a call. You earn the premium but give up gains above the strike. Reduces risk slightly, does not remove it."),
        ("Protective put", "Own the stock and buy a put as insurance. You pay the premium to cap the downside."),
        ("Bull call / bear put spread", "Buy one option and sell a further one: capped profit, capped loss, cheaper than a single option."),
        ("Long straddle", "Buy a call and a put at the same strike: profit from a big move in either direction, lose the premium if the price stays still."),
        ("Short straddle", "Sell both: collect premium if the price stays put, but losses are unlimited on either side. Not suitable for beginners."),
        ("Iron condor", "Sell a close call and put, buy farther ones as protection: profits if the price stays in a range, with capped loss."),
    ]:
        with st.expander(title):
            st.write(text)
    term("Call & put option")
    term("Lot size")
