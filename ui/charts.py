"""Plotly charts. Fixed categorical colours by entity, thin lines, one axis per panel, no dual axes."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ui.common import AQUA, BLUE, ORANGE, RED, VIOLET

UP, DOWN = AQUA, RED
GRID = "rgba(128,128,128,0.15)"


def _layout(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=30, b=0), hovermode="x unified",
                      legend=dict(orientation="h", y=1.04, x=0), xaxis_rangeslider_visible=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def _gaps(idx: pd.DatetimeIndex) -> list:
    """Dates with no trading (weekends + holidays) so candles sit side by side without empty gaps."""
    if len(idx) < 2:
        return []
    naive = idx.tz_localize(None) if idx.tz is not None else idx
    full = pd.date_range(naive.min().normalize(), naive.max().normalize(), freq="D")
    return list(full.difference(naive.normalize()))


def price_chart(ind: pd.DataFrame, show_ema: bool = True, show_bb: bool = False, show_rsi: bool = True,
                show_macd: bool = True, levels: dict[str, float] | None = None, visible_bars: int = 120) -> go.Figure:
    """Candlestick chart that opens on the most recent `visible_bars` candles (big, readable candles).
    Use the 1M/3M/6M/1Y/All buttons or drag to zoom out; all history stays available."""
    rows = 2 + int(show_rsi) + int(show_macd)
    heights = [0.60, 0.10] + [0.15] * (rows - 2)
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, row_heights=heights, vertical_spacing=0.025)
    fig.add_trace(go.Candlestick(x=ind.index, open=ind["Open"], high=ind["High"], low=ind["Low"], close=ind["Close"],
                                 name="Price", increasing_line_color=UP, decreasing_line_color=DOWN,
                                 increasing_fillcolor=UP, decreasing_fillcolor=DOWN, line=dict(width=1.5),
                                 whiskerwidth=0.6), row=1, col=1)
    if show_ema:
        for col, color, name in (("EMA50", BLUE, "50-day EMA"), ("EMA200", ORANGE, "200-day EMA")):
            if ind[col].notna().any():
                fig.add_trace(go.Scatter(x=ind.index, y=ind[col], name=name, line=dict(color=color, width=2)), row=1, col=1)
    if show_bb and ind["BB_up"].notna().any():
        for col, name in (("BB_up", "Bollinger upper"), ("BB_low", "Bollinger lower")):
            fig.add_trace(go.Scatter(x=ind.index, y=ind[col], name=name, line=dict(color=VIOLET, width=1, dash="dot")), row=1, col=1)
    for label, y in (levels or {}).items():
        fig.add_hline(y=y, line=dict(width=1, dash="dash", color="gray"), annotation_text=label, row=1, col=1)
    vol_colors = [UP if c >= o else DOWN for o, c in zip(ind["Open"], ind["Close"])]
    fig.add_trace(go.Bar(x=ind.index, y=ind["Volume"], name="Volume", marker_color=vol_colors, marker_line_width=0, opacity=0.6), row=2, col=1)
    r = 3
    if show_rsi:
        fig.add_trace(go.Scatter(x=ind.index, y=ind["RSI"], name="RSI", line=dict(color=BLUE, width=2)), row=r, col=1)
        for lv in (30, 70):
            fig.add_hline(y=lv, line=dict(width=1, dash="dot", color="gray"), row=r, col=1)
        fig.update_yaxes(range=[0, 100], row=r, col=1)
        r += 1
    if show_macd:
        hist_colors = [UP if v >= 0 else DOWN for v in ind["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=ind.index, y=ind["MACD_hist"], name="MACD hist", marker_color=hist_colors, marker_line_width=0, opacity=0.5), row=r, col=1)
        fig.add_trace(go.Scatter(x=ind.index, y=ind["MACD"], name="MACD", line=dict(color=BLUE, width=2)), row=r, col=1)
        fig.add_trace(go.Scatter(x=ind.index, y=ind["MACD_signal"], name="Signal", line=dict(color=ORANGE, width=2)), row=r, col=1)

    _layout(fig, 620 + 150 * (rows - 2))
    fig.update_xaxes(rangebreaks=[dict(values=_gaps(ind.index))])
    # open zoomed on the latest candles
    n = min(visible_bars, len(ind))
    if n >= 2:
        fig.update_xaxes(range=[ind.index[-n], ind.index[-1] + (ind.index[-1] - ind.index[-2])])
    # y-axis of the price panel fitted to what is visible
    vis = ind.tail(n)
    lo, hi = float(vis["Low"].min()), float(vis["High"].max())
    pad = (hi - lo) * 0.05 or hi * 0.02
    fig.update_yaxes(range=[lo - pad, hi + pad], row=1, col=1)
    # quick zoom buttons (they step in trading bars so they work with the gap-free axis)
    last = ind.index[-1]
    buttons = []
    for label, k in (("1M", 22), ("3M", 66), ("6M", 132), ("1Y", 252)):
        if len(ind) > k:
            buttons.append(dict(label=label, method="relayout", args=[{"xaxis.range": [str(ind.index[-k]), str(last)], "yaxis.range": [
                float(ind.tail(k)["Low"].min()) * 0.98, float(ind.tail(k)["High"].max()) * 1.02]}]))
    buttons.append(dict(label="All", method="relayout", args=[{"xaxis.range": [str(ind.index[0]), str(last)], "yaxis.range": [
        float(ind["Low"].min()) * 0.98, float(ind["High"].max()) * 1.02]}]))
    fig.update_layout(updatemenus=[dict(type="buttons", direction="right", x=1.0, xanchor="right", y=1.08, yanchor="bottom",
                                        buttons=buttons, showactive=False)])
    fig.update_layout(dragmode="pan")
    return fig


def line_chart(series: dict[str, pd.Series], title: str = "", height: int = 380, yfmt: str | None = None) -> go.Figure:
    palette = [BLUE, ORANGE, AQUA, VIOLET]
    fig = go.Figure()
    for i, (name, s) in enumerate(series.items()):
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=name, line=dict(color=palette[i % len(palette)], width=2)))
    fig.update_layout(title=title)
    if yfmt:
        fig.update_yaxes(tickformat=yfmt)
    return _layout(fig, height)


def payoff_chart(prices, pnl, spot: float, breakevens: list[float]) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=prices, y=pnl, name="P&L at expiry", line=dict(color=BLUE, width=2)))
    fig.add_hline(y=0, line=dict(width=1, color="gray"))
    fig.add_vline(x=spot, line=dict(width=1, dash="dash", color="gray"), annotation_text="Spot")
    for b in breakevens:
        fig.add_vline(x=b, line=dict(width=1, dash="dot", color=ORANGE), annotation_text=f"BE {b:,.0f}")
    fig.update_xaxes(title="Price at expiry")
    fig.update_yaxes(title="Profit / loss (₹)")
    return _layout(fig, 380)
