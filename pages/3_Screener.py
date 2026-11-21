import pandas as pd
import streamlit as st

from core.demo import demo_prices
from datasources.fundamentals import get_fundamentals
from datasources.yahoo import DataSourceError, fetch_many
from markets.india import MARKET
from scoring.fundamental import fundamental_analysis
from scoring.technical import technical_analysis
from ui.common import setup

demo = setup("Screener", "🔎")
st.write("Scan many stocks at once and shortlist by trend and momentum. Use the Stock Investing page to dig into any result.")

c1, c2 = st.columns([1, 2])
mode = c1.radio("Universe", ["NIFTY 50", "Custom list"])
if mode == "NIFTY 50":
    syms = MARKET.universe()
    c2.caption(f"{len(syms)} large-cap stocks. (Verify constituents on niftyindices.com: the index changes twice a year.)")
else:
    raw = c2.text_area("Symbols (comma or new line separated)", "TCS, INFY, IRCTC, ZOMATO, DIXON", height=100)
    syms = list(dict.fromkeys(s.strip().upper() for s in raw.replace("\n", ",").split(",") if s.strip()))
    if len(syms) > 100:
        st.warning("Only the first 100 symbols are scanned.")
        syms = syms[:100]

with_fund = st.checkbox("Also scan fundamentals (P/E, ROE, fundamental score)", False)
if with_fund:
    st.warning("Fundamentals need one slow request per stock (about 1-2 seconds each) and Yahoo may rate-limit you. Use a short list.")

run = st.button("Run scan", type="primary", disabled=not syms)


def scan(symbols: list[str], fundamentals: bool) -> tuple[pd.DataFrame, list[str]]:
    rows, failed = [], []
    bar = st.progress(0.0, text="Fetching prices...")
    ymap = {s: MARKET.to_yahoo(s) for s in symbols}
    data: dict[str, pd.DataFrame] = {}
    if demo:
        data = {s: demo_prices(s, "2y") for s in symbols}
    else:
        try:
            got = fetch_many(list(ymap.values()), "2y")
            data = {s: got[y] for s, y in ymap.items() if y in got}
        except DataSourceError as e:
            bar.empty()
            st.error(f"{e}. Check your network or try again later.")
            return pd.DataFrame(), list(symbols)
    for i, s in enumerate(symbols):
        bar.progress((i + 1) / len(symbols), text=f"Analysing {s} ({i + 1}/{len(symbols)})")
        df = data.get(s)
        if df is None or df.empty:
            failed.append(s)
            continue
        analysis, ind, _ = technical_analysis(df)
        if ind.empty:
            failed.append(s)
            continue
        close = float(ind["Close"].iloc[-1])
        rsi = ind["RSI"].dropna()
        e200 = ind["EMA200"].dropna()
        row = {
            "Symbol": s,
            "Last close": round(close, 2),
            "Tech score": analysis.score,
            "Verdict": analysis.verdict,
            "RSI": round(float(rsi.iloc[-1]), 1) if not rsi.empty else None,
            "Above 200 EMA": bool(close > float(e200.iloc[-1])) if not e200.empty else None,
            "% from 52w high": round((close / float(df["High"].tail(252).max()) - 1) * 100, 1),
        }
        if fundamentals:
            try:
                info = get_fundamentals(s, demo)
            except Exception:
                info = None
            fa, _ = fundamental_analysis(info)
            row["P/E"] = round(info["pe"], 1) if info and info.get("pe") is not None else None
            row["ROE %"] = round(info["roe"] * 100, 1) if info and info.get("roe") is not None else None
            row["Fund score"] = fa.score if info else None
        rows.append(row)
    bar.empty()
    return pd.DataFrame(rows), failed


if run:
    result, failed = scan(syms, with_fund)
    st.session_state["screener"] = (result, failed, demo)

state = st.session_state.get("screener")
if state:
    result, failed, was_demo = state
    if was_demo != demo:
        st.info("Data mode changed since the last scan: run the scan again.")
    elif result.empty:
        st.warning("No results. " + (f"Failed: {', '.join(failed[:15])}" if failed else ""))
    else:
        st.subheader("Filter results")
        f1, f2, f3 = st.columns(3)
        min_score = f1.slider("Min technical score", 0, 100, 60)
        above = f2.checkbox("Only above 200-day EMA", True)
        rlo, rhi = f3.slider("RSI range", 0, 100, (40, 75))
        out = result[result["Tech score"] >= min_score]
        if above:
            out = out[out["Above 200 EMA"] == True]  # noqa: E712
        out = out[out["RSI"].between(rlo, rhi) | out["RSI"].isna()]
        out = out.sort_values("Tech score", ascending=False)
        st.caption(f"{len(out)} of {len(result)} stocks match.")
        st.dataframe(out, hide_index=True, width="stretch")
        st.download_button("Download CSV", out.to_csv(index=False).encode(), "screener.csv", "text/csv")
        if failed:
            st.caption(f"No data for: {', '.join(failed[:20])}{'...' if len(failed) > 20 else ''}")
        if was_demo:
            st.error("DEMO MODE results are synthetic.")
        st.caption("A high score means the price trend is healthy, not that the business is good or the price is cheap. Open the stock for the full report.")
