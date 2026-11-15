"""Render tool results (KPIs, Plotly chart, table, Analysis Details) inside the chat."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from letura.ai.tools import ChartSpec, ToolResult
from letura.ui import components as C

KPI_MAP = {
    "get_market_summary": [("listings", "Listings", "{:,.0f}"), ("median_rent_per_sqm", "Median €/m²", "€{:,.2f}"),
                           ("mean_rent_per_sqm", "Mean €/m²", "€{:,.2f}"), ("median_living_space_sqm", "Median area", "{:,.1f} m²")],
    "get_rent_trends": [("first_median", "First median €/m²", "€{:,.2f}"), ("last_median", "Last median €/m²", "€{:,.2f}"),
                        ("change_pct_between_medians", "Change in medians", "{:+.1f}%")],
    "get_rent_distribution": [("n", "Listings", "{:,.0f}"), ("median", "Median €/m²", "€{:,.2f}"), ("p90", "P90 €/m²", "€{:,.2f}"),
                              ("iqr_outliers_flagged", "IQR outliers (kept)", "{:,.0f}")],
    "get_data_quality_report": [("checks_total", "Checks", "{:,.0f}"), ("checks_pass", "Pass", "{:,.0f}"), ("checks_warn", "Warnings", "{:,.0f}")],
    "get_mietenspiegel_benchmark": [("cells_returned", "Benchmark cells", "{:,.0f}"), ("median_reference_rent", "Median reference €/m²", "€{:,.2f}"),
                                    ("highest_max", "Highest max €/m²", "€{:,.2f}")],
}


def build_figure(spec: ChartSpec, df: pd.DataFrame):
    if spec.x not in df.columns or (spec.y and spec.y not in df.columns) or df.empty:
        return None
    if spec.y and df[spec.y].dropna().empty:
        return None
    k = spec.kind
    if k == "line":
        return C.line(df, spec.x, spec.y, spec.title, color=spec.color, ylabel=spec.ylabel, order=spec.order)
    if k in {"bar", "hbar"}:
        fig = C.bar(df, spec.x, spec.y, spec.title, xlabel=spec.xlabel, ylabel=spec.ylabel, horizontal=(k == "hbar"), color=spec.color, order=spec.order)
        if spec.color:
            fig.update_layout(barmode="group")
        return fig
    if k == "scatter":
        return C.scatter(df, spec.x, spec.y, spec.title, color=spec.color, xlabel=spec.xlabel, ylabel=spec.ylabel)
    if k == "hist":
        return C.hist(df, spec.x, spec.title, spec.xlabel)
    if k == "box":
        return C.box(df, spec.x, spec.y, spec.title)
    return None


def render_result(res: ToolResult, key: str) -> None:
    if not res.ok:
        st.warning(f"`{res.tool}`: {res.error}")
        return
    if res.tool in KPI_MAP:
        items = []
        for k, label, fmt in KPI_MAP[res.tool]:
            v = res.summary.get(k)
            if v is not None:
                items.append((label, fmt.format(v), ""))
        if items:
            C.kpi_row(items)
    df = res.frame()
    if res.chart is not None:
        fig = build_figure(res.chart, df)
        if fig is not None:
            C.show(fig, 340, f"{key}_chart")
    if not df.empty:
        with st.expander(f"Table · {res.title} ({len(df)} rows)", expanded=len(df) <= 12 and res.chart is None):
            st.dataframe(df, hide_index=True, width="stretch")
            C.download_csv(df, f"{res.tool}.csv", key=f"{key}_dl")
    with st.expander("Analysis Details"):
        st.markdown(f"- **Data source:** {res.source}\n- **Filters applied:** {res.filters_applied or '–'}\n- **Date / snapshot context:** {res.period or '–'}\n"
                    f"- **Records analysed:** {res.n_records:,}\n- **Metric calculation:** {res.calculation or '–'}")
        for c in res.caveats:
            st.caption(f"⚠ {c}")
