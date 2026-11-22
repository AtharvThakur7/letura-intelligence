"""Dashboard – the executive view: headline KPIs, auto-generated business insights and the four
charts that matter most, combined from Market, Neighbourhoods, Properties and Official rents."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import shared
from letura.analytics import repo, transforms as T
from letura.i18n import t
from letura.ui import components as C


def _page(url_path: str):
    return next((p for p in st.session_state.get("_pages", []) if p.url_path == url_path), None)


def _delta_pct(first: float, last: float) -> float | None:
    if not first:
        return None
    return round(100 * (last - first) / first, 1)


def _ms_comparison(df: pd.DataFrame):
    """Historical median vs. official 2025 reference, by construction period. None if unavailable."""
    try:
        ref = repo.load_table("analytics_mietenspiegel_reference")
    except Exception:  # noqa: BLE001
        return None, None
    h = df.dropna(subset=["ms_construction_period"])
    if h.empty:
        return None, None
    hist_by_period = h.groupby("ms_construction_period")["rent_per_sqm"].median()
    ref_by_period = ref.groupby("construction_period")["reference_rent_per_sqm"].median()
    common = hist_by_period.index.intersection(ref_by_period.index)
    if not len(common):
        return None, None
    gap = float((hist_by_period[common] - ref_by_period[common]).median())
    long = pd.DataFrame({
        "period": list(common) * 2,
        "series": [t("Historical asking rent (2018–20)")] * len(common) + [t("Official reference (2025)")] * len(common),
        "value": list(hist_by_period[common]) + list(ref_by_period[common]),
    })
    long["o"] = long["period"].map(T.MS_PERIODS.index)
    long = long.sort_values("o")
    return gap, long


def render() -> None:
    C.page_header(t("Dashboard"), t("The Hamburg rental market at a glance — the numbers that matter most, in one view."))
    df_all = shared.load_listings_or_stop()
    f = shared.current_filters(df_all)
    df = shared.filtered(df_all, f)
    if df.empty:
        C.empty_state()
        return
    df = df.assign(snapshot=df["snapshot"].astype(str))

    trend = df.groupby("snapshot", observed=True)["rent_per_sqm"].median().reindex(T.SNAPSHOT_ORDER).dropna()
    delta = _delta_pct(float(trend.iloc[0]), float(trend.iloc[-1])) if len(trend) >= 2 else None
    nb = df.groupby("neighbourhood")["rent_per_sqm"].median().dropna()
    matched = df[df["location_class"].notna()]
    match_share = 100 * len(matched) / len(df)
    ms_gap, ms_long = _ms_comparison(df)

    # ---- headline KPIs, in real-estate business terms. Custom cards (not native st.metric): every
    # color and background here comes from our own theme tokens, so dark mode is always correct —
    # a native widget's internal chart/number rendering can silently stay light-themed underneath.
    r1 = st.columns(3)
    with r1[0]:
        C.metric_card(t("Median Asking Rent"), C.eur_sqm(df["rent_per_sqm"].median()), icon="💶",
                      delta=f"{delta:+.1f}%" if delta is not None else None,
                      delta_kind=("good" if delta is not None and delta >= 0 else "bad") if delta is not None else "neutral",
                      spark=C.sparkline(trend.tolist()) if len(trend) >= 2 else None, key="dash_spark_rent",
                      help=t("The core pricing benchmark: the midpoint of advertised cold rent per square metre "
                            "across listings in view. The change compares the first to the last snapshot shown."))
    with r1[1]:
        C.metric_card(t("Active Listings"), f"{len(df):,}", icon="🏠",
                      help=t("Live inventory matching your current filters — the size of the market you're viewing."))
    with r1[2]:
        C.metric_card(t("Avg. Unit Size"), f"{df['livingSpace'].mean():,.0f} m²", icon="📐",
                      help=t("Average living area across listings in view — a quick read on typical unit size in this market."))

    r2 = st.columns(3)
    with r2[0]:
        C.metric_card(t("Neighbourhoods Covered"), f"{df['neighbourhood'].nunique()}", icon="🗺️",
                      help=t("Distinct Hamburg neighbourhoods represented in view — breadth of market coverage."))
    with r2[1]:
        C.metric_card(t("Location-Quality Match Rate"), f"{match_share:.0f}%", icon="📍",
                      help=t("Share of listings matched to Hamburg's official street-level location-quality register — "
                            "data reliability for location-based pricing."))
    with r2[2]:
        C.metric_card(t("Premium vs. Official Benchmark"), f"{ms_gap:+.2f} €/m²" if ms_gap is not None else "–",
                      icon="⚖️", delta_kind="neutral",
                      help=t("Median gap between advertised asking rents and the 2025 Mietenspiegel reference for "
                            "matching construction periods — how the market prices above or below the official "
                            "benchmark. Contextual only — different periods and methods."))

    # ---- auto-generated business insights
    insights = []
    if delta is not None:
        insights.append(t("Median rent moved **{delta:+.1f}%** from {first} to {last}.",
                          delta=delta, first=trend.index[0], last=trend.index[-1]))
    if len(nb) >= 2:
        top_nb, bottom_nb = nb.idxmax(), nb.idxmin()
        insights.append(t("**{top}** is the most expensive neighbourhood in view at {top_v}; "
                          "**{bottom}** is the most affordable at {bottom_v}.",
                          top=top_nb, top_v=C.eur_sqm(nb[top_nb]), bottom=bottom_nb, bottom_v=C.eur_sqm(nb[bottom_nb])))
    if ms_gap is not None:
        direction = t("above") if ms_gap > 0 else t("below")
        insights.append(t("Advertised rents run **{gap} €/m² {direction}** the official 2025 reference rent for "
                          "comparable flats, on average.", gap=f"{abs(ms_gap):.2f}", direction=direction))
    if insights:
        C.section(t("What the data tells us"))
        for i in insights:
            st.markdown(f"- {i}")

    # ---- the four charts that matter most, combined from the other pages
    C.section(t("The market, combined"))
    c1, c2 = st.columns(2)
    with c1:
        tr = df.groupby("snapshot", observed=True)["rent_per_sqm"].agg(median="median", n="count").reset_index()
        fig = C.line(tr, "snapshot", "median", t("Median rent over time (€/m²)"), ylabel="€/m²", order=T.SNAPSHOT_ORDER)
        fig.update_traces(customdata=tr[["n"]], hovertemplate="%{x}<br>Median €%{y:.2f}/m²<br>%{customdata[0]} listings<extra></extra>")
        C.show(fig, 320, "dash_trend")
    with c2:
        top8 = C.summary_table(df, "neighbourhood", "Neighbourhood").sort_values("Median €/m²", ascending=False).head(8)
        C.show(C.bar(top8, "Neighbourhood", "Median €/m²", t("Most expensive neighbourhoods (€/m²)"),
                     horizontal=True, hover=["Listings"]), 320, "dash_nb")

    c1, c2 = st.columns(2)
    with c1:
        tdf = df.assign(property_type=df["property_type"].fillna(t("Not stated")))
        order = tdf.groupby("property_type")["rent_per_sqm"].median().sort_values(ascending=False).index.tolist()
        C.show(C.box(tdf, "property_type", "rent_per_sqm", t("Rent per m² by property type"), order=order), 320, "dash_pt")
    with c2:
        if ms_long is not None:
            fig = C.bar(ms_long, "period", "value", t("Historical rents vs. official 2025 reference"), color="series", ylabel="€/m²")
            fig.update_layout(barmode="group", xaxis_tickangle=-30, legend_title_text="")
            C.show(fig, 320, "dash_ms")
        else:
            C.empty_state(t("Official reference data is unavailable right now."))

    # ---- explore further
    C.section(t("Explore further"))
    links = [("market", t("Market"), ":material/insights:"), ("neighbourhoods", t("Neighbourhoods"), ":material/location_city:"),
             ("properties", t("Properties"), ":material/apartment:"), ("official-rents", t("Official rents"), ":material/balance:"),
             ("ask-ai", t("Letura AI"), ":material/smart_toy:")]
    cols = st.columns(len(links))
    for col, (url_path, label, icon) in zip(cols, links):
        pg = _page(url_path)
        if pg is not None:
            with col:
                st.page_link(pg, label=label, icon=icon, width="stretch")

    st.caption(t("Based on historical asking rents (2018–2020) and official 2025 reference rents. "
                 "Not current prices and not a legal rent determination."))
