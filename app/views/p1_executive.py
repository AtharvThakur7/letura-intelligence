"""Market overview: the headline picture, kept to four charts."""
from __future__ import annotations

import streamlit as st

from app import shared
from letura.analytics import transforms as T
from letura.ui import components as C


def render() -> None:
    C.page_header("Market overview", "How advertised rents look across Hamburg.")
    df_all = shared.load_listings_or_stop()
    f = shared.current_filters(df_all)
    df = shared.filtered(df_all, f)
    if df.empty:
        C.empty_state()
        return

    C.kpi_row([
        ("Listings", C.num(len(df)), f"{df['neighbourhood'].nunique()} neighbourhoods", "Number of listings matching your filters."),
        ("Median rent", C.eur_sqm(df["rent_per_sqm"].median()), "cold rent per m²", "Middle value of advertised base rent ÷ living area. Excludes service charges and heating."),
        ("Average rent", C.eur_sqm(df["rent_per_sqm"].mean()), "pulled up by luxury flats", "Average; a few expensive listings raise it above the median."),
        ("Typical size", f"{df['livingSpace'].median():,.0f} m²", f"{df['noRooms'].median():g} rooms", "Median living area and number of rooms."),
    ])

    c1, c2 = st.columns(2)
    with c1:
        tr = df.groupby("snapshot", observed=True)["rent_per_sqm"].agg(median="median", n="count").reset_index()
        tr["snapshot"] = tr["snapshot"].astype(str)
        fig = C.line(tr, "snapshot", "median", "Median rent over time (€/m²)", ylabel="€/m²", order=T.SNAPSHOT_ORDER)
        fig.update_traces(customdata=tr[["n"]], hovertemplate="%{x}<br>Median €%{y:.2f}/m²<br>%{customdata[0]} listings<extra></extra>")
        C.show(fig, 330, "p1_trend")
    with c2:
        C.show(C.hist(df, "rent_per_sqm", "How rents are spread (€/m²)", "€/m²"), 330, "p1_hist")

    c1, c2 = st.columns(2)
    with c1:
        C.show(C.hist(df, "livingSpace", "Flat sizes (m²)", "m²", nbins=40), 330, "p1_size")
    with c2:
        p = df["property_type"].fillna("Not stated").value_counts().reset_index()
        p.columns = ["Property type", "Listings"]
        C.show(C.bar(p, "Property type", "Listings", "Property types", horizontal=True, text="Listings"), 330, "p1_type")

    st.caption("Advertised cold rents from four snapshots between Sep 2018 and Feb 2020. Each snapshot has different listings, so this is not the same flats over time, and not current prices.")
