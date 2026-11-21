from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from ipo.scoring import COLUMNS, NUMERIC, analyse_ipo, application_amount, clean, estimated_listing_price, status
from ui.common import level_box, money, setup, term

demo = setup("IPO", "🆕")

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "ipo" / "ipos_sample.csv"

st.warning(
    "**Rows marked `sample = True` are ILLUSTRATIVE, not real IPOs.** There is no free, reliable API for IPO data, so "
    "real IPOs must be entered by you from the RHP / prospectus and the NSE/BSE IPO pages (upload a CSV or use the form below)."
)

# ----------------------------------------------------------------------------- data in session
if "ipo_df" not in st.session_state:
    try:
        st.session_state["ipo_df"] = clean(pd.read_csv(SAMPLE_PATH))
    except Exception as e:  # missing/corrupt sample file
        st.error(f"Could not load the sample IPO file: {e}")
        st.session_state["ipo_df"] = clean(pd.DataFrame(columns=COLUMNS))

with st.expander("📥 Load, add or export IPO data", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Upload a CSV (replaces the current table)**")
        up = st.file_uploader("IPO CSV", type=["csv"], key="ipo_upload", label_visibility="collapsed")
        if up is not None and st.button("Use uploaded file"):
            try:
                raw = pd.read_csv(up)
            except Exception as e:
                st.error(f"Could not read the CSV: {e}")
            else:
                if "name" not in raw.columns:
                    st.error("The CSV must have a `name` column. Download the template for the expected columns.")
                else:
                    unknown = [c for c in raw.columns if c not in COLUMNS]
                    new = clean(raw)
                    if new.empty:
                        st.error("No usable rows found (every row needs a name).")
                    else:
                        st.session_state["ipo_df"] = new
                        st.success(f"Loaded {len(new)} IPO(s)." + (f" Ignored unknown columns: {', '.join(unknown)}." if unknown else ""))
                        st.rerun()
        st.download_button("Download CSV template", pd.DataFrame(columns=COLUMNS).to_csv(index=False),
                           file_name="ipo_template.csv", mime="text/csv")
        if st.button("Reset to the bundled sample data"):
            st.session_state["ipo_df"] = clean(pd.read_csv(SAMPLE_PATH))
            st.rerun()
    with c2:
        st.markdown("**Add an IPO** (leave unknown numbers blank: they are treated as 'not available', never as zero)")
        with st.form("add_ipo", clear_on_submit=False):
            name = st.text_input("Company / IPO name")
            exchange = st.selectbox("Exchange", ["Mainboard", "SME"])
            d1, d2, d3 = st.columns(3)
            open_d = d1.date_input("Opens", value=date.today(), key="ipo_open")
            close_d = d2.date_input("Closes", value=date.today(), key="ipo_close")
            list_d = d3.date_input("Listing", value=date.today(), key="ipo_list")
            nums: dict[str, str] = {}
            cols = st.columns(3)
            for i, col in enumerate(NUMERIC):
                nums[col] = cols[i % 3].text_input(col, key=f"ipo_in_{col}")
            if st.form_submit_button("Add IPO"):
                row, bad = {"name": name.strip(), "exchange": exchange, "open_date": open_d, "close_date": close_d,
                            "listing_date": list_d, "sample": False}, []
                for k, v in nums.items():
                    v = v.strip()
                    if v:
                        try:
                            row[k] = float(v)
                        except ValueError:
                            bad.append(k)
                if not row["name"]:
                    st.error("Name is required.")
                elif bad:
                    st.error(f"Not a number: {', '.join(bad)}")
                elif close_d < open_d or list_d < close_d:
                    st.error("Dates must satisfy: open <= close <= listing.")
                else:
                    st.session_state["ipo_df"] = clean(pd.concat([st.session_state["ipo_df"], pd.DataFrame([row])], ignore_index=True))
                    st.success(f"Added {row['name']}.")
                    st.rerun()

df: pd.DataFrame = st.session_state["ipo_df"]
if df.empty:
    st.info("No IPOs loaded. Upload a CSV or add one above.")
    st.stop()
df = df.copy()
df["status"] = df.apply(status, axis=1)

# ----------------------------------------------------------------------------- calendar
st.subheader("IPO calendar")
f1, f2 = st.columns(2)
statuses = sorted(df["status"].unique())
sel_status = f1.multiselect("Status", statuses, default=statuses)
exchanges = sorted(df["exchange"].unique())
sel_ex = f2.multiselect("Exchange", exchanges, default=exchanges)
view = df[df["status"].isin(sel_status) & df["exchange"].isin(sel_ex)]
cal_cols = ["name", "exchange", "status", "open_date", "close_date", "listing_date", "price_band_low", "price_band_high",
            "lot_size", "issue_size_cr", "sample"]
st.dataframe(view[cal_cols], width="stretch", hide_index=True)
if view.empty:
    st.info("No IPOs match these filters.")
    st.stop()

# ----------------------------------------------------------------------------- analysis
st.subheader("IPO analysis")
name = st.selectbox("Choose an IPO to analyse", view["name"].tolist())
row = view[view["name"] == name].iloc[0]
analysis, coverage = analyse_ipo(row)

if bool(row["sample"]):
    st.error("This is SAMPLE data: illustrative only. Do not use this verdict for a real application.")

level = {"Apply": "success", "Apply with caution": "warning", "Avoid": "error"}.get(analysis.verdict, "info")
level_box(level, f"### Verdict: {analysis.verdict}")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Score", f"{analysis.score:.0f}/100")
m2.metric("Rule coverage", f"{coverage:.0%}", help="Share of rule weight that had data. Low coverage = fill in more fields from the RHP.")
m3.metric("Status", row["status"])
amt = application_amount(row)
m4.metric("1 lot at upper band", money(amt) if amt is not None else "n/a")
if amt is not None:
    st.caption(f"Retail applications are capped at ₹2 lakh per application ({'within' if amt <= 200_000 else 'ABOVE'} the cap for 1 lot). "
               "Your money is blocked (ASBA) until allotment; unallotted funds are released.")

est = estimated_listing_price(row)
if est is not None:
    st.info(f"Grey-market-implied listing price: **{money(est)}**. GMP is unofficial, unregulated and easily manipulated: "
            "use it only as a mood indicator. Actual listing prices can differ widely or even be below the issue price.")

rt = pd.DataFrame([{"Rule": r.rule, "Result": ("✅ passed" if r.passed else "❌ not met") if r.available else "➖ no data",
                    "Points": r.points if r.available else None, "Max": r.max_points, "Why": r.detail} for r in analysis.reasons])
st.markdown("**Why this verdict**")
st.dataframe(rt, width="stretch", hide_index=True)

if analysis.risks:
    st.markdown("**Risks and cautions**")
    for r in analysis.risks:
        st.write(f"⚠️ {r}")

with st.expander("📋 What to read in the RHP before applying"):
    st.markdown(
        "- **Objects of the issue**: where the money goes (debt repayment vs growth capex vs general purposes)\n"
        "- **Fresh issue vs Offer for Sale** and who is selling\n"
        "- **Financials for 3-5 years**: revenue, profit, cash flow from operations, receivables\n"
        "- **Peer comparison** table and the issue P/E against listed peers\n"
        "- **Risk factors**: litigation, customer/supplier concentration, regulatory dependence\n"
        "- **Promoters**: background, pledges, related-party transactions, past issues\n"
        "- **Anchor investors** and lock-in periods\n"
        "- **Auditor remarks / qualifications** and any change of auditors"
    )

with st.expander("ℹ️ Learn: IPO terms", expanded=False):
    for t in ("IPO", "Fresh issue vs OFS", "GMP", "Anchor investors / QIB", "Allotment"):
        term(t)
