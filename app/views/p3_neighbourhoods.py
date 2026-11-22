"""Neighbourhoods: ranking, comparison, districts and location quality, in four tabs."""
from __future__ import annotations

import streamlit as st

from app import shared
from letura.analytics import transforms as T
from letura.i18n import t
from letura.ui import components as C

LOCATION_LABELS = {"normal": "Normal location", "gut": "Good location"}


def render() -> None:
    C.page_header(t("Neighbourhoods"), t("Which parts of Hamburg are expensive, and how they compare."))
    df_all = shared.load_listings_or_stop()
    f = shared.current_filters(df_all)
    df = shared.filtered(df_all, f)
    if df.empty:
        C.empty_state()
        return
    df = df.assign(snapshot=df["snapshot"].astype(str))

    c1, c2 = st.columns([2, 3])
    metric = c1.segmented_control(t("Rank by"), ["Median €/m²", "Mean €/m²"], default="Median €/m²", key="nb_metric") or "Median €/m²"
    with c2.expander(t("Options")):
        min_n = st.slider(t("Hide neighbourhoods with fewer listings than"), 1, 50, 10,
                          help=t("Medians based on very few listings are unreliable, so small neighbourhoods are hidden by default."))
    tbl = C.summary_table(df, "neighbourhood", "Neighbourhood")
    ranked = tbl[tbl["Listings"] >= min_n].sort_values(metric, ascending=False)
    if ranked.empty:
        C.empty_state(t("No neighbourhood has enough listings. Lower the minimum in Options."))
        return

    tab_rank, tab_compare, tab_district, tab_loc = st.tabs(
        [t("Ranking"), t("Compare"), t("Districts"), t("Location quality")])

    with tab_rank:
        C.kpi_row([
            (t("Most expensive"), ranked.iloc[0]["Neighbourhood"], C.eur_sqm(ranked.iloc[0][metric])),
            (t("Most affordable"), ranked.sort_values(metric).iloc[0]["Neighbourhood"], C.eur_sqm(ranked.sort_values(metric).iloc[0][metric])),
            (t("Most listings"), tbl.sort_values("Listings", ascending=False).iloc[0]["Neighbourhood"],
             t("{n} listings", n=int(tbl['Listings'].max()))),
        ])
        top = ranked.head(15)
        C.show(C.bar(top, "Neighbourhood", metric, f"Top 15 by {metric.lower()}", horizontal=True, hover=["Listings", "P25", "P75"]),
               max(340, 24 * len(top) + 90), "p3_rank")
        with st.expander(t("Full table")):
            shown = ranked.copy()
            shown.insert(0, "Rank", range(1, len(shown) + 1))
            st.dataframe(shown, hide_index=True, width="stretch", height=360)
            C.download_csv(tbl, "neighbourhoods.csv", key="p3_dl")
        st.caption(t("{n} neighbourhoods with fewer than {min_n} listings are hidden.", n=len(tbl) - len(ranked), min_n=min_n))

    with tab_compare:
        default = ranked.sort_values("Listings", ascending=False).head(5)["Neighbourhood"].tolist()
        sel = st.multiselect(t("Choose neighbourhoods"), sorted(tbl["Neighbourhood"]), default=default)
        if sel:
            sub = df[df["neighbourhood"].isin(sel)]
            order = sub.groupby("neighbourhood")["rent_per_sqm"].median().sort_values(ascending=False).index.tolist()
            c1, c2 = st.columns(2)
            with c1:
                C.show(C.box(sub, "neighbourhood", "rent_per_sqm", t("Rent range (€/m²)"), order=order), 360, "p3_box")
            with c2:
                tr = sub.groupby(["snapshot", "neighbourhood"]).agg(median=("rent_per_sqm", "median"), n=("rent_per_sqm", "size")).reset_index()
                C.show(C.line(tr, "snapshot", "median", t("Median over time (€/m²)"), color="neighbourhood", ylabel="€/m²", order=T.SNAPSHOT_ORDER), 360, "p3_trend")
            st.dataframe(tbl[tbl["Neighbourhood"].isin(sel)].sort_values("Median €/m²", ascending=False), hide_index=True, width="stretch")
            if (tr["n"] < 10).any():
                st.caption(t("Some points rest on fewer than 10 listings and are only indicative."))
        else:
            C.empty_state(t("Pick at least one neighbourhood."))

    with tab_district:
        bz = C.summary_table(df.dropna(subset=["bezirk"]), "bezirk", "District").sort_values("Median €/m²", ascending=False)
        c1, c2 = st.columns([3, 2])
        with c1:
            C.show(C.bar(bz, "District", "Median €/m²", t("Median rent by district (€/m²)"), text="Median €/m²"), 340, "p3_bezirk")
        with c2:
            st.dataframe(bz[["District", "Listings", "Median €/m²", "P25", "P75"]], hide_index=True, width="stretch")

    with tab_loc:
        st.caption(t("Hamburg's official 2025 list marks streets as normal or good residential locations. "
                   "A listing gets a class only when its street and house number match the list exactly. "
                   "The list is from 2025; the listings are 2018–2020."))
        matched = df[df["location_class"].notna()]
        share = 100 * len(matched) / len(df)
        C.kpi_row([(t("Listings with a location class"), f"{len(matched):,}", t("{pct}% of listings in view", pct=f"{share:.0f}")),
                   (t("Without one"), f"{len(df) - len(matched):,}", t("no street or number, or no exact match"))])
        if matched["location_class"].nunique() < 2:
            C.empty_state(t("Not enough matched listings in view to compare good and normal locations."))
        else:
            m = matched.assign(location=matched["location_class"].map(lambda k: t(LOCATION_LABELS.get(k, k))))
            c1, c2 = st.columns([3, 2])
            with c1:
                C.show(C.box(m, "location", "rent_per_sqm", t("Rent by location quality (€/m²)")), 330, "p3_loc")
            with c2:
                st.dataframe(C.summary_table(m, "location", "Location"), hide_index=True, width="stretch")
        st.caption(t("No map is shown because the data has no exact coordinates."))
