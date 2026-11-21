"""Shared UI helpers: page setup, demo toggle, data-quality panel, glossary hints."""
from __future__ import annotations

import streamlit as st

from learn.glossary import lookup

DISCLAIMER = ("Educational analysis from fixed, explainable rules. Not investment advice and not SEBI-registered advice. "
              "Free data can be wrong or delayed: verify prices on NSE or your broker before acting.")

# Validated categorical palette (light-mode steps) - fixed order, never cycled.
BLUE, ORANGE, AQUA, VIOLET, RED, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#e34948", "#eda100"


def setup(title: str, icon: str) -> bool:
    """Call first on every page. Returns True when demo (synthetic) data mode is on."""
    st.set_page_config(page_title=f"{title} | Market Understanding Lab", page_icon=icon, layout="wide")
    with st.sidebar:
        st.markdown("### Market Understanding Lab")
        demo = st.toggle("Demo data (synthetic)", key="demo_mode",
                         help="Uses made-up prices so you can explore the app offline. NOT real market data.")
        if demo:
            st.warning("DEMO MODE: all numbers are synthetic.")
        st.caption(DISCLAIMER)
    st.title(f"{icon} {title}")
    if demo:
        st.error("DEMO MODE: prices and fundamentals on this page are synthetic and meaningless for decisions.")
    return bool(demo)


def show_checks(checks, as_of: str = "", sources: list[str] | None = None) -> None:
    st.caption(f"Data as of {as_of or 'n/a'} | Sources: {', '.join(sources or []) or 'n/a'}")
    failed = [c for c in checks if not c.ok]
    if failed:
        st.warning(f"{len(failed)} data check(s) failed: verify on NSE before relying on these numbers.")
    for c in checks:
        st.write(f"{'✅' if c.ok else '❌'} **{c.name}**: {c.detail}")


def term(name: str) -> None:
    """Inline 'what does this mean?' expander."""
    t = lookup(name)
    if t:
        with st.expander(f"ℹ️ What is {name}?"):
            st.write(t[1])
            st.write(f"**How to use it:** {t[2]}")


def level_box(level: str, text: str) -> None:
    {"success": st.success, "info": st.info, "warning": st.warning, "error": st.error}.get(level, st.info)(text)


def money(x: float | None, cur: str = "₹") -> str:
    return "n/a" if x is None else f"{cur}{x:,.2f}"


def pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"
