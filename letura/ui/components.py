"""Reusable Streamlit components & chart builders (shared by every page)."""
from __future__ import annotations

import html
from typing import Iterable

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from letura.analytics import stats
from letura.i18n import t
from letura.ui import theme

HISTORICAL_NOTE = ("Historical advertised cold rents (ImmoScout24 snapshots, Sep 2018 – Feb 2020). "
                   "Independent snapshots – not the same properties tracked over time and not current 2026 rents.")
BENCHMARK_CAVEAT = ("These datasets differ in reference period, population and methodology. This comparison is contextual, "
                    "not a same-period market premium or legal rent determination.")


def mode() -> str:
    return st.session_state.get("theme_mode", "light")


def eur(x, d: int = 0) -> str:
    return "–" if x is None or pd.isna(x) else f"€{x:,.{d}f}"


def eur_sqm(x, d: int = 2) -> str:
    return "–" if x is None or pd.isna(x) else f"€{x:,.{d}f}/m²"


def num(x, d: int = 0) -> str:
    return "–" if x is None or pd.isna(x) else f"{x:,.{d}f}"


def page_header(title: str, description: str) -> None:
    st.markdown(f'<h1 class="lt-title">{html.escape(title)}</h1><p class="lt-desc">{html.escape(description)}</p>',
                unsafe_allow_html=True)


def section(title: str, help: str | None = None) -> None:
    st.markdown(f'<div class="lt-section">{html.escape(title)}</div>', unsafe_allow_html=True)
    if help:
        st.caption(help)


def banner(text: str, kind: str = "warn") -> None:
    st.markdown(f'<div class="lt-banner {kind}">{html.escape(t(text))}</div>', unsafe_allow_html=True)


def kpi(label: str, value: str, sub: str = "", help: str = "") -> str:
    return (f'<div class="lt-kpi" title="{html.escape(help)}"><div class="l">{html.escape(label)}</div>'
            f'<div class="v">{html.escape(value)}</div><div class="s">{html.escape(sub)}&nbsp;</div></div>')


def kpi_row(items: Iterable[tuple]) -> None:
    items = list(items)
    for c, it in zip(st.columns(len(items)), items):
        with c:
            st.markdown(kpi(*it), unsafe_allow_html=True)
    st.write("")


def pills(labels: Iterable[tuple[str, str]]) -> None:
    st.markdown("".join(f'<span class="lt-pill {k}">{html.escape(t)}</span>' for t, k in labels), unsafe_allow_html=True)


def empty_state(msg: str | None = None) -> None:
    banner(msg or "No listings match the current filters. Widen or reset the filters.", "info")


def download_csv(df: pd.DataFrame, filename: str, label: str | None = None, key: str | None = None) -> None:
    st.download_button(t(label or "Download CSV"), csv_bytes(df), file_name=filename, mime="text/csv",
                       key=key or f"dl_{filename}", disabled=df.empty)


def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


def show(fig: go.Figure, height: int = 360, key: str | None = None) -> None:
    theme.style_fig(fig, mode(), height)
    st.plotly_chart(fig, theme=None, width="stretch", key=key, config={"displaylogo": False, "responsive": True})


# ---------------------------------------------------------------- chart builders
def hist(df: pd.DataFrame, col: str, title: str, xlabel: str, nbins: int = 40, median: bool = True) -> go.Figure:
    tok = theme.tokens(mode())
    fig = px.histogram(df, x=col, nbins=nbins, title=title, color_discrete_sequence=[tok["series"][0]])
    fig.update_traces(marker_line_width=0, hovertemplate=f"{xlabel}: %{{x}}<br>Listings: %{{y}}<extra></extra>")
    if median and df[col].notna().any():
        m = df[col].median()
        fig.add_vline(x=m, line_dash="dash", line_color=tok["text2"], annotation_text=f"Median {m:,.2f}",
                      annotation_font_color=tok["text2"])
    fig.update_layout(xaxis_title=xlabel, yaxis_title=t("Listings"), showlegend=False)
    return fig


def bar(df: pd.DataFrame, x: str, y: str, title: str, xlabel: str = "", ylabel: str = "", horizontal: bool = False,
        text: str | None = None, color: str | None = None, hover: list[str] | None = None,
        order: list[str] | None = None) -> go.Figure:
    tok = theme.tokens(mode())
    kw = dict(x=y, y=x, orientation="h") if horizontal else dict(x=x, y=y)
    fig = px.bar(df, title=title, color=color, color_discrete_sequence=tok["series"] if color else [tok["series"][0]],
                 hover_data=hover, text=text, category_orders={x: order} if order else None, **kw)
    fig.update_traces(marker_line_width=0, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=ylabel if horizontal else xlabel, yaxis_title=xlabel if horizontal else ylabel)
    if horizontal:
        fig.update_yaxes(autorange="reversed")
    return fig


def box(df: pd.DataFrame, x: str, y: str, title: str, order: list[str] | None = None, xlabel: str = "",
        ylabel: str = "€/m²") -> go.Figure:
    tok = theme.tokens(mode())
    fig = px.box(df, x=x, y=y, title=title, points="outliers", color_discrete_sequence=[tok["series"][0]],
                 category_orders={x: order} if order else None)
    fig.update_traces(marker=dict(size=4, opacity=.55))
    fig.update_layout(xaxis_title=xlabel, yaxis_title=ylabel, showlegend=False)
    return fig


def scatter(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None, xlabel: str = "",
            ylabel: str = "", hover: list[str] | None = None, trend: bool = False) -> go.Figure:
    tok = theme.tokens(mode())
    fig = px.scatter(df, x=x, y=y, color=color, title=title, hover_data=hover, opacity=.65,
                     color_discrete_sequence=tok["series"])
    fig.update_traces(marker=dict(size=6, line=dict(width=0)))
    d = df.dropna(subset=[x, y])
    if trend and len(d) > 12 and d[x].nunique() > 3:
        bins = pd.qcut(d[x], q=min(12, d[x].nunique()), duplicates="drop")
        tr = d.groupby(bins, observed=True).agg(bx=(x, "median"), by=(y, "median"))
        fig.add_trace(go.Scatter(x=tr.bx, y=tr.by, mode="lines+markers", name="Binned median",
                                 line=dict(color=tok["text"], width=2),
                                 marker=dict(size=7, line=dict(color=tok["surface"], width=2))))
    fig.update_layout(xaxis_title=xlabel, yaxis_title=ylabel)
    return fig


def line(df: pd.DataFrame, x: str, y: str, title: str, color: str | None = None, ylabel: str = "",
         order: list[str] | None = None) -> go.Figure:
    tok = theme.tokens(mode())
    fig = px.line(df, x=x, y=y, color=color, title=title, markers=True, color_discrete_sequence=tok["series"],
                  category_orders={x: order} if order else None)
    fig.update_traces(line=dict(width=2.5), marker=dict(size=9, line=dict(color=tok["surface"], width=2)))
    fig.update_layout(yaxis_title=ylabel, xaxis_title="")
    return fig


def summary_table(df: pd.DataFrame, by: str, label: str, value: str = "rent_per_sqm") -> pd.DataFrame:
    """Listings / median / mean / P25 / P75 / min / max per group; small samples are flagged, never hidden."""
    g = stats.grouped_describe(df, by, value)
    if g.empty:
        return g
    g = g[[by, "n", "median", "mean", "p25", "p75", "min", "max", "sample_flag"]].rename(columns={
        by: label, "n": "Listings", "median": "Median €/m²", "mean": "Mean €/m²", "p25": "P25", "p75": "P75",
        "min": "Min", "max": "Max", "sample_flag": "Sample"})
    g["Sample"] = g["Sample"].map({"ok": "OK", "small": "⚠ small (n<10)", "very_small": "⚠ very small (n<5)"})
    return g.round(2)
