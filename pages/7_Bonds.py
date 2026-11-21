import pandas as pd
import streamlit as st

from bonds.calc import after_tax_yield, current_yield, duration, price_from_ytm, ytm_from_price
from ui import charts
from ui.common import pct, setup, term

setup("Bonds", "📜")
st.info("There is **no live bond-price feed** in this app. Enter the price you see on the exchange (NSE/BSE debt segment), "
        "your broker, or RBI Retail Direct. All maths below is exact for the numbers you type in.")

calc, risk, tax, ladder, basics = st.tabs(["Price ↔ YTM", "Duration & rate risk", "After-tax vs FD", "Ladder", "Learn the basics"])


def bond_inputs(prefix: str):
    c1, c2, c3, c4 = st.columns(4)
    face = c1.number_input("Face value (₹)", 1.0, 10_000_000.0, 1000.0, 100.0, key=f"{prefix}_face")
    coupon = c2.number_input("Coupon rate (% a year)", 0.0, 30.0, 7.5, 0.05, key=f"{prefix}_coupon") / 100
    years = c3.number_input("Years to maturity", 0.5, 40.0, 5.0, 0.5, key=f"{prefix}_years")
    freq = c4.selectbox("Coupons per year", [1, 2, 4, 12], index=1, key=f"{prefix}_freq")
    return face, coupon, years, freq


with calc:
    st.subheader("Price ↔ yield to maturity")
    term("YTM")
    face, coupon, years, freq = bond_inputs("calc")
    mode = st.radio("I know the...", ["Yield (YTM): find the fair price", "Price: find the YTM"], horizontal=True)
    if mode.startswith("Yield"):
        ytm = st.number_input("Yield to maturity (%)", 0.0, 40.0, 7.0, 0.05) / 100
        price = price_from_ytm(face, coupon, years, ytm, freq)
    else:
        price = st.number_input("Quoted price (₹ per face value)", 1.0, 10_000_000.0, 1000.0, 1.0)
        ytm = ytm_from_price(price, face, coupon, years, freq)
        if ytm is None:
            st.warning("No sensible yield exists for that price (outside -50% to 200%). Re-check the inputs.")
    if ytm is not None:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Price", f"₹{price:,.2f}")
        m2.metric("Yield to maturity", pct(ytm, 2))
        m3.metric("Current yield", pct(current_yield(price, face, coupon), 2))
        m4.metric("Premium / discount", f"{(price / face - 1) * 100:+.2f}%")
        if price > face:
            st.caption("Trades at a **premium**: coupon is higher than the market yield, so YTM is below the coupon rate.")
        elif price < face:
            st.caption("Trades at a **discount**: coupon is lower than the market yield, so YTM is above the coupon rate.")
        else:
            st.caption("Trades at **par**: YTM equals the coupon rate.")

with risk:
    st.subheader("How much does the price fall if interest rates rise?")
    term("Duration")
    face, coupon, years, freq = bond_inputs("risk")
    ytm = st.number_input("Current market yield (%)", 0.0, 40.0, 7.0, 0.05, key="risk_ytm") / 100
    d = duration(face, coupon, years, ytm, freq)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Price", f"₹{d['price']:,.2f}")
    m2.metric("Macaulay duration", f"{d['macaulay']:.2f} yrs")
    m3.metric("Modified duration", f"{d['modified']:.2f}")
    m4.metric("Price change per +1% yield", f"₹{d['price_change_per_1pct']:,.2f}")
    shocks = [-0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02]
    rows = []
    for s in shocks:
        p = price_from_ytm(face, coupon, years, max(ytm + s, 0.0), freq)
        rows.append({"Yield change": f"{s * 100:+.1f}%", "New yield": pct(ytm + s, 2), "Price (₹)": round(p, 2),
                     "Price change": f"{(p / d['price'] - 1) * 100:+.2f}%"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    grid = [max(ytm + x / 1000, 0.0) for x in range(-30, 31, 2)]
    curve = pd.Series([price_from_ytm(face, coupon, years, g, freq) for g in grid], index=[g * 100 for g in grid])
    fig = charts.line_chart({"Price": curve}, "Price vs yield (the curve bends: gains from a fall in rates exceed losses from an equal rise)")
    fig.update_xaxes(title="Yield (%)")
    fig.update_yaxes(title="Price (₹)")
    st.plotly_chart(fig, width="stretch", key="bond_curve")
    st.caption("Longer maturity and lower coupon mean higher duration, so more sensitivity to interest-rate changes.")

with tax:
    st.subheader("Is the bond really better than a fixed deposit, after tax?")
    c1, c2, c3 = st.columns(3)
    bond_y = c1.number_input("Bond yield (YTM, %)", 0.0, 40.0, 8.0, 0.05) / 100
    fd_y = c2.number_input("Bank FD rate (%)", 0.0, 20.0, 7.0, 0.05) / 100
    slab = c3.selectbox("Your income-tax slab", [0, 5, 10, 15, 20, 30], index=5, format_func=lambda x: f"{x}%") / 100
    tax_free = st.checkbox("The bond's interest is tax-free (e.g. certain tax-free PSU bonds)")
    b_after = bond_y if tax_free else after_tax_yield(bond_y, slab)
    f_after = after_tax_yield(fd_y, slab)
    m1, m2, m3 = st.columns(3)
    m1.metric("Bond after-tax yield", pct(b_after, 2))
    m2.metric("FD after-tax yield", pct(f_after, 2))
    m3.metric("Advantage of bond", f"{(b_after - f_after) * 100:+.2f} pts")
    if b_after > f_after:
        st.success("The bond beats the FD after tax, but check credit risk: an FD is insured up to ₹5 lakh per bank by DICGC, a bond is not.")
    else:
        st.warning("The FD matches or beats the bond after tax, with lower risk. The extra risk of the bond is not being paid for.")
    st.caption("Simplified: ignores capital-gains tax on bonds sold before maturity, TDS timing, and reinvestment of coupons.")

with ladder:
    st.subheader("Bond ladder illustration")
    st.write("A ladder splits money across bonds that mature in successive years. As each rung matures you reinvest at "
             "then-current rates, reducing the risk of locking everything in at one rate.")
    c1, c2, c3 = st.columns(3)
    amount = c1.number_input("Total to invest (₹)", 10_000.0, 100_000_000.0, 1_000_000.0, 10_000.0)
    rungs = c2.slider("Number of rungs (years)", 3, 10, 5)
    base_y = c3.number_input("Yield on 1-year rung (%)", 0.0, 20.0, 6.8, 0.05) / 100
    slope = st.slider("Extra yield per extra year of maturity (pts)", 0.0, 0.5, 0.1, 0.05) / 100
    per = amount / rungs
    rows = [{"Rung": i + 1, "Matures in (years)": i + 1, "Amount (₹)": round(per),
             "Assumed yield": base_y + slope * i, "Yearly interest (₹)": round(per * (base_y + slope * i))} for i in range(rungs)]
    df = pd.DataFrame(rows)
    st.dataframe(df.assign(**{"Assumed yield": df["Assumed yield"].map(lambda v: pct(v, 2))}), hide_index=True, width="stretch")
    avg = float((df["Assumed yield"] * per).sum() / amount)
    m1, m2, m3 = st.columns(3)
    m1.metric("Average yield", pct(avg, 2))
    m2.metric("Yearly interest (approx.)", f"₹{df['Yearly interest (₹)'].sum():,.0f}")
    m3.metric("Cash back every year", f"₹{per:,.0f}")
    st.bar_chart(df.set_index("Matures in (years)")["Amount (₹)"])

with basics:
    st.subheader("The main types of bonds in India")
    for title, text in [
        ("Government securities (G-Secs)", "Issued by the central government; carry no default risk. Tenors from about 5 to 40 years. Buy via RBI Retail Direct or your broker."),
        ("Treasury bills (T-bills)", "Short-term (91, 182, 364 days) government paper sold at a discount to face value. Used for parking money safely."),
        ("State Development Loans (SDLs)", "Issued by state governments. Slightly higher yield than G-Secs for slightly more risk."),
        ("Corporate bonds / NCDs", "Issued by companies; pay more than government paper to compensate for default risk. Liquidity on the exchange can be thin."),
        ("Sovereign Gold Bonds (SGBs)", "Government securities denominated in grams of gold: you earn about 2.5% interest plus gold-price changes. Maturity redemption is tax-free for individuals (verify)."),
    ]:
        with st.expander(title):
            st.write(text)
    st.subheader("Credit ratings and why yield rises with risk")
    st.dataframe(pd.DataFrame([
        {"Rating": "AAA", "Meaning": "Highest safety", "Typical extra yield over G-Secs": "Lowest"},
        {"Rating": "AA", "Meaning": "High safety", "Typical extra yield over G-Secs": "Low"},
        {"Rating": "A", "Meaning": "Adequate safety", "Typical extra yield over G-Secs": "Moderate"},
        {"Rating": "BBB", "Meaning": "Moderate safety (lowest 'investment grade')", "Typical extra yield over G-Secs": "Higher"},
        {"Rating": "BB and below", "Meaning": "Speculative: significant default risk", "Typical extra yield over G-Secs": "High"},
        {"Rating": "D", "Meaning": "In default", "Typical extra yield over G-Secs": "n/a"},
    ]), hide_index=True, width="stretch")
    st.write("Investors will only lend to a riskier borrower if they are paid more. That extra yield is the **credit spread**. "
             "A very high yield is usually the market telling you the default risk is high, not a bargain. "
             "Check the rating agency's latest rationale (CRISIL, ICRA, CARE, India Ratings) before buying.")
