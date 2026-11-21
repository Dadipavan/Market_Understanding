import streamlit as st

from learn.glossary import GLOSSARY, categories
from ui.common import setup

setup("Learn", "📚")

glossary_tab, roadmap_tab, mistakes_tab = st.tabs(["Glossary", "Beginner roadmap", "Common mistakes"])

with glossary_tab:
    c1, c2 = st.columns([1, 2])
    cat = c1.selectbox("Category", ["All"] + categories())
    q = c2.text_input("Search a term or word", placeholder="e.g. stop-loss, P/E, SIP").strip().lower()
    shown = 0
    for term_name, (category, meaning, how) in GLOSSARY.items():
        if cat != "All" and category != cat:
            continue
        if q and q not in term_name.lower() and q not in meaning.lower() and q not in how.lower():
            continue
        shown += 1
        with st.expander(f"{term_name}  ·  {category}"):
            st.markdown(f"**What it means:** {meaning}")
            st.markdown(f"**How to use it:** {how}")
    if shown == 0:
        st.info("No matching terms. Try a shorter search or the 'All' category.")
    else:
        st.caption(f"{shown} term(s) shown.")

with roadmap_tab:
    st.subheader("A simple, repeatable process")
    steps = [
        ("1. Know your goal and risk profile", "How much can you invest, for how long, and what fall (e.g. -20%) could you sit through without panic-selling? Money needed within 3 years should not be in stocks."),
        ("2. Check the market context", "Is NIFTY above its 200-day average? Is India VIX calm or spiking? Market weather changes how aggressively you should act."),
        ("3. Build a shortlist", "Use the Screener to find 5-10 candidates (quality + reasonable valuation, or strong trend). Do not research 500 stocks."),
        ("4. Analyse each candidate", "Read the advisor report: business quality, valuation, trend, and the listed risks. Verify key numbers on NSE and Screener.in."),
        ("5. Size the position", "Decide the stop first, then size so that a stop-out costs only 1-2% of capital. Keep any single stock under about 20% of your portfolio."),
        ("6. Record the trade in a journal", "Write why you bought, your stop and target, and what would change your mind. Practise on paper first."),
        ("7. Review monthly", "Compare with NIFTY, check win rate and costs, and read your notes. Fix process mistakes, not just outcomes."),
    ]
    for title, text in steps:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.write(text)
    st.caption("Mapping to this app: roadmap steps 3-4 use Stock Investing and the Screener, step 5 and 6 use Trading and the paper portfolio.")

with mistakes_tab:
    st.subheader("Mistakes that cost beginners the most")
    for title, text in [
        ("Trading without a stop-loss", "One bad position can erase months of gains. Decide the exit before you enter."),
        ("Oversizing", "Putting 30-50% of capital into one idea turns a normal loss into a disaster."),
        ("Chasing tips and sudden jumps", "By the time a stock is on social media, much of the move is usually done."),
        ("Averaging down on a falling stock", "Adding to a loser because 'it is cheaper now' without re-checking the thesis."),
        ("Ignoring costs and taxes", "Frequent trading can lose to STT, brokerage and short-term capital gains tax even when you are right more often than wrong."),
        ("Over-trading F&O", "Roughly 9 in 10 individual F&O traders lose money. Leverage magnifies mistakes."),
        ("Judging by a short period", "A few trades or a single backtest tell you almost nothing. Look for hundreds of observations and out-of-sample results."),
        ("Applying to every IPO for listing gains", "Listing pops are not guaranteed; weak, expensive IPOs often list flat or below issue price."),
        ("Trusting one data source blindly", "Free data can be stale or wrong. Cross-check prices and fundamentals before acting."),
    ]:
        with st.expander(title):
            st.write(text)
