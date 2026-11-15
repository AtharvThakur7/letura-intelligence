"""Page 2 – Rental Market Explorer."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import shared
from letura.analytics import stats, transforms as T
from letura.analytics.filters import AMENITIES
from letura.ui import components as C

TABLE_COLUMNS = {
    "snapshot": "Snapshot", "neighbourhood": "Neighbourhood", "property_type": "Type", "baseRent": "Base rent €",
    "livingSpace": "Area m²", "noRooms": "Rooms", "rent_per_sqm": "€/m²", "yearConstructed": "Year built",
    "street_decoded": "Street", "geo_plz": "PLZ", "outlier_iqr_global": "Outlier (IQR)", "quality_flags": "Quality flags",
}


def listing_table(df: pd.DataFrame, key: str, filename: str) -> None:
    """Searchable, sortable listing table + CSV export. Outliers are flagged, never removed."""
    q = st.text_input("Search listings (neighbourhood, street, type, PLZ)", key=f"{key}_q", placeholder="e.g. Eppendorf")
    only_flagged = st.checkbox("Show only flagged records (outliers / quality flags)", key=f"{key}_flag")
    t = df
    if q:
        hay = (t["neighbourhood"].fillna("") + " " + t["street_decoded"].fillna("") + " " + t["property_type"].fillna("")
               + " " + t["geo_plz"].fillna(""))
        t = t[hay.str.contains(q.strip(), case=False, regex=False)]
    if only_flagged:
        t = t[t["is_flagged"].astype(bool)]
    out = t[list(TABLE_COLUMNS)].rename(columns=TABLE_COLUMNS).copy()
    out["Snapshot"] = out["Snapshot"].astype(str)
    st.caption(f"{len(out):,} listings shown. Click a column header to sort.")
    st.dataframe(out, width="stretch", hide_index=True, height=380, column_config={
        "€/m²": st.column_config.NumberColumn(format="%.2f"), "Base rent €": st.column_config.NumberColumn(format="%.0f"),
        "Year built": st.column_config.NumberColumn(format="%d")})
    C.download_csv(out, filename, "Download filtered listings (CSV)", key=f"{key}_dl")


def render() -> None:
    C.page_header("Rental Market Explorer", "Explore advertised rent per m² and property characteristics in detail.")
    df_all = shared.load_listings_or_stop()
    f = shared.current_filters(df_all)
    df = shared.filtered(df_all, f)
    C.banner(C.HISTORICAL_NOTE, "info")
    if df.empty:
        C.empty_state()
        return

    d = stats.describe(df["rent_per_sqm"])
    C.kpi_row([
        ("Sample size", C.num(d["n"]), "listings with rent/m²"),
        ("Median", C.eur_sqm(d["median"]), f"mean {C.eur_sqm(d['mean'])}"),
        ("P25 – P75", f"€{d['p25']:.2f} – €{d['p75']:.2f}", f"IQR €{d['iqr']:.2f}"),
        ("P90 / P95", f"€{d['p90']:.2f} / €{d['p95']:.2f}", "upper-tail context"),
        ("Min – Max", f"€{d['min']:.2f} – €{d['max']:.2f}", f"{int((df['outlier_iqr_global'] != 'normal').sum())} IQR outliers (kept)"),
    ])

    c1, c2 = st.columns(2)
    with c1:
        C.show(C.hist(df, "rent_per_sqm", "Rent per m² distribution", "€/m²"), 340, "p2_hist")
    with c2:
        sc = df.copy()
        sc["Outlier"] = sc["outlier_iqr_global"].map({"normal": "Within IQR fences", "high": "High outlier (flagged)", "low": "Low outlier (flagged)"})
        sc["snapshot"] = sc["snapshot"].astype(str)
        C.show(C.scatter(sc, "livingSpace", "rent_per_sqm", "Rent per m² vs living area", color="Outlier",
                         xlabel="Living area (m²)", ylabel="€/m²", hover=["neighbourhood", "snapshot", "noRooms"], trend=True),
               340, "p2_scatter")

    c1, c2 = st.columns(2)
    with c1:
        C.show(C.box(df, "room_band", "rent_per_sqm", "Rent per m² by number of rooms", order=T.ROOM_BAND_ORDER, xlabel="Rooms"), 340, "p2_rooms")
    with c2:
        types = df.assign(property_type=df["property_type"].fillna("Unknown"))
        order = types.groupby("property_type")["rent_per_sqm"].median().sort_values(ascending=False).index.tolist()
        C.show(C.box(types, "property_type", "rent_per_sqm", "Rent per m² by property type", order=order), 340, "p2_type")

    c1, c2 = st.columns(2)
    with c1:
        C.section("Rent comparison by amenity", "Median €/m² with vs without each feature. Association only – not a causal effect.")
        rows = []
        for col, label in AMENITIES.items():
            for val, name in [(True, "With"), (False, "Without")]:
                s = df.loc[df[col] == val, "rent_per_sqm"]
                rows.append({"Amenity": label, "Group": name, "Median €/m²": s.median() if len(s) else None, "Listings": len(s)})
        am = pd.DataFrame(rows).dropna(subset=["Median €/m²"])
        fig = C.bar(am, "Amenity", "Median €/m²", "Median rent with / without amenity", color="Group", hover=["Listings"])
        fig.update_layout(barmode="group")
        fig.update_traces(textposition="none")
        C.show(fig, 340, "p2_amen")
    with c2:
        C.section("Listings by snapshot")
        n = df.groupby("snapshot", observed=True).size().reset_index(name="Listings")
        n["snapshot"] = n["snapshot"].astype(str)
        C.show(C.bar(n, "snapshot", "Listings", "Listings per snapshot", order=T.SNAPSHOT_ORDER, text="Listings"), 340, "p2_n")

    C.section("Summary statistics by room count and snapshot")
    t1, t2 = st.tabs(["By room count", "By snapshot"])
    with t1:
        st.dataframe(C.summary_table(df, "room_band", "Rooms"), hide_index=True, width="stretch")
    with t2:
        s = C.summary_table(df.assign(snapshot=df["snapshot"].astype(str)), "snapshot", "Snapshot")
        s["_o"] = s["Snapshot"].map(T.SNAPSHOT_ORDER.index)
        st.dataframe(s.sort_values("_o").drop(columns="_o"), hide_index=True, width="stretch")

    C.section("Listing-level data")
    listing_table(df, "p2", "letura_listings_filtered.csv")
