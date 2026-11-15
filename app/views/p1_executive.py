"""Page 1 – Executive Overview."""
from __future__ import annotations

import streamlit as st

from app import shared
from letura.analytics import transforms as T
from letura.ui import components as C


def render() -> None:
    C.page_header("Executive Overview", "High-level view of the Hamburg rental market based on historical advertised rents.")
    df_all = shared.load_listings_or_stop()
    f = shared.current_filters(df_all)
    df = shared.filtered(df_all, f)
    C.banner(C.HISTORICAL_NOTE, "info")
    if df.empty:
        C.empty_state()
        return

    snaps = df["snapshot"].astype(str).nunique()
    C.kpi_row([
        ("Rental listings", C.num(len(df)), f"{snaps} snapshot(s) · {df['neighbourhood'].nunique()} neighbourhoods",
         "Number of Hamburg listings matching the filters."),
        ("Median cold rent", C.eur_sqm(df["rent_per_sqm"].median()), "advertised base rent ÷ living area",
         "Median of baseRent / livingSpace. Excludes service charges and heating."),
        ("Average cold rent", C.eur_sqm(df["rent_per_sqm"].mean()), "mean – sensitive to outliers",
         "Arithmetic mean; pulled upward by high-priced listings, which are retained."),
        ("Median living area", f"{df['livingSpace'].median():,.1f} m²", f"P25–P75: {df['livingSpace'].quantile(.25):.0f}–{df['livingSpace'].quantile(.75):.0f} m²"),
        ("Median rooms", f"{df['noRooms'].median():g}", f"P25–P75: {df['noRooms'].quantile(.25):g}–{df['noRooms'].quantile(.75):g}"),
    ])

    c1, c2 = st.columns(2)
    with c1:
        C.section("Historical median rent per m²", "Four independent snapshots – different listings in each.")
        tr = df.groupby("snapshot", observed=True)["rent_per_sqm"].agg(
            median="median", p25=lambda s: s.quantile(.25), p75=lambda s: s.quantile(.75), n="count").reset_index()
        tr["snapshot"] = tr["snapshot"].astype(str)
        fig = C.line(tr, "snapshot", "median", "Median advertised rent (€/m²)", ylabel="€/m²", order=T.SNAPSHOT_ORDER)
        fig.update_traces(customdata=tr[["n", "p25", "p75"]], hovertemplate="%{x}<br>Median €%{y:.2f}/m²<br>n=%{customdata[0]}<br>P25–P75 €%{customdata[1]:.2f}–€%{customdata[2]:.2f}<extra></extra>")
        C.show(fig, 340, "p1_trend")
    with c2:
        C.section("Listings by snapshot")
        n = df.groupby("snapshot", observed=True).size().reset_index(name="Listings")
        n["snapshot"] = n["snapshot"].astype(str)
        C.show(C.bar(n, "snapshot", "Listings", "Listings per snapshot", order=T.SNAPSHOT_ORDER, text="Listings"), 340, "p1_n")

    c1, c2 = st.columns(2)
    with c1:
        C.section("Rental price distribution")
        C.show(C.hist(df, "rent_per_sqm", "Advertised rent per m²", "€/m²"), 340, "p1_hist")
    with c2:
        C.section("Distribution of apartment sizes")
        C.show(C.hist(df, "livingSpace", "Living area", "m²", nbins=40), 340, "p1_size")

    c1, c2 = st.columns(2)
    with c1:
        C.section("Distribution by number of rooms")
        r = df.groupby("room_band", observed=True).size().reset_index(name="Listings")
        C.show(C.bar(r, "room_band", "Listings", "Listings by room count", xlabel="Rooms", order=T.ROOM_BAND_ORDER, text="Listings"), 320, "p1_rooms")
    with c2:
        C.section("Property type distribution")
        p = df["property_type"].fillna("Unknown").value_counts().reset_index()
        p.columns = ["Property type", "Listings"]
        C.show(C.bar(p, "Property type", "Listings", "Listings by property type", horizontal=True, text="Listings"), 320, "p1_type")

    C.section("Highest median-rent neighbourhoods", "Only neighbourhoods with at least 10 listings in the current selection.")
    nb = C.summary_table(df, "neighbourhood", "Neighbourhood")
    nb = nb[nb["Listings"] >= 10].sort_values("Median €/m²", ascending=False)
    if nb.empty:
        C.empty_state("No neighbourhood has ≥10 listings under the current filters.")
    else:
        top = nb.head(12)
        C.show(C.bar(top, "Neighbourhood", "Median €/m²", "Top neighbourhoods by median rent", horizontal=True, text="Median €/m²", hover=["Listings"]), 420, "p1_nbh")
        C.download_csv(nb, "executive_neighbourhoods.csv", key="dl_p1")
