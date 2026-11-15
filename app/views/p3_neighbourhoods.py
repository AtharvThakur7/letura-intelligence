"""Page 3 – Neighbourhood Analysis."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import shared
from letura.analytics import stats, transforms as T
from letura.ui import components as C


def render() -> None:
    C.page_header("Neighbourhood Analysis", "Compare advertised rents across Hamburg neighbourhoods (Stadtteile) and districts (Bezirke).")
    df_all = shared.load_listings_or_stop()
    f = shared.current_filters(df_all)
    df = shared.filtered(df_all, f)
    C.banner(C.HISTORICAL_NOTE, "info")
    if df.empty:
        C.empty_state()
        return
    df = df.assign(snapshot=df["snapshot"].astype(str))

    c1, c2, c3 = st.columns([1, 1, 1])
    min_n = c1.slider("Minimum listings per neighbourhood", 1, 50, 10, help="Neighbourhoods below this size are hidden from rankings to avoid misleading medians.")
    metric = c2.radio("Rank by", ["Median €/m²", "Mean €/m²"], horizontal=True)
    top_n = c3.slider("Neighbourhoods shown in charts", 5, 40, 15)

    tbl = C.summary_table(df, "neighbourhood", "Neighbourhood")
    ranked = tbl[tbl["Listings"] >= min_n].sort_values(metric, ascending=False)
    hidden = len(tbl) - len(ranked)
    C.kpi_row([
        ("Neighbourhoods shown", f"{len(ranked)}", f"{hidden} hidden (n < {min_n})"),
        ("Highest median", ranked.iloc[0]["Neighbourhood"] if len(ranked) else "–", C.eur_sqm(ranked["Median €/m²"].max()) if len(ranked) else ""),
        ("Lowest median", ranked.sort_values("Median €/m²").iloc[0]["Neighbourhood"] if len(ranked) else "–",
         C.eur_sqm(ranked["Median €/m²"].min()) if len(ranked) else ""),
        ("Most listings", tbl.sort_values("Listings", ascending=False).iloc[0]["Neighbourhood"], f"{int(tbl['Listings'].max())} listings"),
    ])
    if ranked.empty:
        C.empty_state("No neighbourhood meets the minimum sample size. Lower the threshold.")
        return

    c1, c2 = st.columns(2)
    with c1:
        top = ranked.head(top_n)
        C.show(C.bar(top, "Neighbourhood", metric, f"{metric} by neighbourhood", horizontal=True, hover=["Listings", "P25", "P75"]),
               max(340, 22 * len(top) + 80), "p3_rank")
    with c2:
        vol = tbl.sort_values("Listings", ascending=False).head(top_n)
        C.show(C.bar(vol, "Neighbourhood", "Listings", "Listing volume by neighbourhood", horizontal=True, text="Listings"),
               max(340, 22 * len(vol) + 80), "p3_vol")

    C.section("Neighbourhood ranking table", "Small samples are flagged. Sort by any column.")
    shown = ranked.copy()
    shown.insert(0, "Rank", range(1, len(shown) + 1))
    st.dataframe(shown, hide_index=True, width="stretch", height=380)
    C.download_csv(tbl, "neighbourhood_summary.csv", "Download full neighbourhood table (CSV)", key="p3_dl")

    C.section("Compare neighbourhoods")
    default = ranked.sort_values("Listings", ascending=False).head(6)["Neighbourhood"].tolist()
    sel = st.multiselect("Neighbourhoods to compare", sorted(tbl["Neighbourhood"]), default=default)
    if sel:
        sub = df[df["neighbourhood"].isin(sel)]
        c1, c2 = st.columns(2)
        with c1:
            order = sub.groupby("neighbourhood")["rent_per_sqm"].median().sort_values(ascending=False).index.tolist()
            C.show(C.box(sub, "neighbourhood", "rent_per_sqm", "Rent distribution by neighbourhood", order=order), 380, "p3_box")
        with c2:
            tr = sub.groupby(["snapshot", "neighbourhood"]).agg(median=("rent_per_sqm", "median"), n=("rent_per_sqm", "size")).reset_index()
            fig = C.line(tr, "snapshot", "median", "Median rent trend by snapshot", color="neighbourhood", ylabel="€/m²", order=T.SNAPSHOT_ORDER)
            C.show(fig, 380, "p3_trend")
            thin = tr[tr["n"] < 10]
            if len(thin):
                st.caption(f"⚠ {len(thin)} neighbourhood-snapshot points have fewer than 10 listings; treat their medians as indicative.")
        st.dataframe(tbl[tbl["Neighbourhood"].isin(sel)].sort_values("Median €/m²", ascending=False), hide_index=True, width="stretch")

    C.section("District (Bezirk) comparison")
    bz = C.summary_table(df.dropna(subset=["bezirk"]), "bezirk", "Bezirk").sort_values("Median €/m²", ascending=False)
    c1, c2 = st.columns([3, 2])
    with c1:
        C.show(C.bar(bz, "Bezirk", "Median €/m²", "Median rent by district", text="Median €/m²", hover=["Listings"]), 320, "p3_bezirk")
    with c2:
        st.dataframe(bz[["Bezirk", "Listings", "Median €/m²", "Mean €/m²", "P25", "P75"]], hide_index=True, width="stretch")

    C.section("Residential location classes (Wohnlagenverzeichnis 2025)",
              "Matched conservatively by street + house-number range + odd/even numbering. Unmatched or ambiguous addresses are NOT assigned a class.")
    cov = df["location_match_status"].value_counts().rename_axis("Match status").reset_index(name="Listings")
    cov["Share"] = (100 * cov["Listings"] / len(df)).round(1).astype(str) + "%"
    matched = df[df["location_class"].notna()]
    c1, c2 = st.columns([2, 3])
    with c1:
        st.dataframe(cov, hide_index=True, width="stretch")
        C.banner("The Wohnlagenverzeichnis is a 2025 classification applied to 2018–2020 listings. "
                 "It describes the address's current class, not the class at listing time.", "warn")
    with c2:
        if matched.empty or matched["location_class"].nunique() < 1:
            C.empty_state("No listings could be matched to a residential location class under these filters.")
        else:
            m = matched.assign(location=matched["location_class"].map({"normal": "Normal Wohnlage", "gut": "Gute Wohnlage"}))
            C.show(C.box(m, "location", "rent_per_sqm", "Advertised rent: normal vs good location (matched listings)"), 300, "p3_loc")
    if len(matched):
        lt = C.summary_table(matched.assign(location=matched["location_class"].map({"normal": "Normal Wohnlage", "gut": "Gute Wohnlage"})), "location", "Location class")
        st.dataframe(lt, hide_index=True, width="stretch")
        top = matched.groupby(["neighbourhood", "location_class"]).size().unstack(fill_value=0)
        top["Matched"] = top.sum(axis=1)
        top = top.sort_values("Matched", ascending=False).head(15).reset_index()
        with st.expander("Matched listings by neighbourhood and class"):
            st.dataframe(top, hide_index=True, width="stretch")

    C.section("Geographic view")
    st.info("No reliable coordinates exist in the source data (only postcode, street and neighbourhood name), so a map is intentionally not shown "
            "rather than inventing locations.")
