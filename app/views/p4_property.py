"""Page 4 – Property Insights."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import shared
from app.views.p2_explorer import listing_table
from letura.analytics import stats, transforms as T
from letura.analytics.filters import AMENITIES
from letura.ui import components as C


def render() -> None:
    C.page_header("Property Insights", "How advertised rent per m² varies with property characteristics. Associations only – no causal claims.")
    df_all = shared.load_listings_or_stop()
    f = shared.current_filters(df_all)
    df = shared.filtered(df_all, f)
    C.banner(C.HISTORICAL_NOTE + " Patterns below are descriptive associations; size, location, age and quality are correlated with each other.", "info")
    if df.empty:
        C.empty_state()
        return
    df = df.assign(snapshot=df["snapshot"].astype(str))

    C.section("Data coverage", "Share of filtered listings with a usable value for each characteristic.")
    cov = pd.DataFrame({
        "Characteristic": ["Living area", "Rooms", "Construction year (plausible)", "Property type", "Balcony", "Garden", "Lift", "Kitchen", "New construction"],
        "Available": [df["livingSpace"].notna().sum(), df["noRooms"].notna().sum(), df["year_band"].notna().sum(),
                      df["property_type"].notna().sum(), df["has_balcony"].notna().sum(), df["has_garden"].notna().sum(),
                      df["has_lift"].notna().sum(), df["has_kitchen"].notna().sum(), df["is_new_construction"].notna().sum()]})
    cov["Coverage %"] = (100 * cov["Available"] / len(df)).round(1)
    cov["Missing"] = len(df) - cov["Available"]
    c1, c2 = st.columns([3, 2])
    with c1:
        C.show(C.bar(cov, "Characteristic", "Coverage %", "Coverage of characteristics (%)", horizontal=True, text="Coverage %"), 330, "p4_cov")
    with c2:
        st.dataframe(cov, hide_index=True, width="stretch")

    tabs = st.tabs(["Size & rooms", "Construction year", "Property type", "Amenities", "New vs existing", "Listings"])

    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            C.show(C.scatter(df, "livingSpace", "rent_per_sqm", "Rent per m² vs living area", xlabel="Living area (m²)", ylabel="€/m²",
                             hover=["neighbourhood", "snapshot"], trend=True), 360, "p4_s1")
        with c2:
            C.show(C.scatter(df, "livingSpace", "baseRent", "Base rent (€) vs living area", xlabel="Living area (m²)", ylabel="Base rent €",
                             hover=["neighbourhood", "snapshot"], trend=True), 360, "p4_s2")
        c1, c2 = st.columns(2)
        with c1:
            C.show(C.box(df, "size_band", "rent_per_sqm", "Rent per m² by size band", order=T.SIZE_BAND_ORDER), 340, "p4_sb")
        with c2:
            C.show(C.box(df, "room_band", "rent_per_sqm", "Rent per m² by room count", order=T.ROOM_BAND_ORDER, xlabel="Rooms"), 340, "p4_rb")
        sub = df.dropna(subset=["livingSpace", "rent_per_sqm"])
        if len(sub) > 10:
            rho = stats.spearman(sub["livingSpace"], sub["rent_per_sqm"])
            st.caption(f"Spearman rank correlation, living area vs rent/m²: **{rho:.2f}** (n={len(sub):,}). Descriptive only.")
        st.dataframe(C.summary_table(df, "size_band", "Size band").assign(_o=lambda d: d["Size band"].map(T.SIZE_BAND_ORDER.index)).sort_values("_o").drop(columns="_o"),
                     hide_index=True, width="stretch")

    with tabs[1]:
        y = df.dropna(subset=["yearConstructed"])
        implausible = y[(y["yearConstructed"] < T.MIN_PLAUSIBLE_YEAR) | (y["yearConstructed"] > T.MAX_PLAUSIBLE_YEAR + 1)]
        yp = y.drop(implausible.index)
        st.caption(f"{len(df) - len(y):,} listings have no construction year; {len(implausible)} have an implausible year (kept in the data, excluded from this chart).")
        if len(yp) < 5:
            C.empty_state("Not enough listings with construction year under these filters.")
        else:
            C.show(C.scatter(yp, "yearConstructed", "rent_per_sqm", "Rent per m² vs construction year", xlabel="Construction year", ylabel="€/m²",
                             hover=["neighbourhood", "snapshot"], trend=True), 380, "p4_year")
            C.show(C.box(yp, "year_band", "rent_per_sqm", "Rent per m² by construction period", order=T.YEAR_BAND_ORDER), 340, "p4_yb")
            st.dataframe(C.summary_table(yp, "year_band", "Construction period").assign(_o=lambda d: d["Construction period"].map(T.YEAR_BAND_ORDER.index)).sort_values("_o").drop(columns="_o"),
                         hide_index=True, width="stretch")

    with tabs[2]:
        t = df.assign(property_type=df["property_type"].fillna("Unknown / not stated"))
        order = t.groupby("property_type")["rent_per_sqm"].median().sort_values(ascending=False).index.tolist()
        c1, c2 = st.columns(2)
        with c1:
            C.show(C.box(t, "property_type", "rent_per_sqm", "Rent per m² by property type", order=order), 380, "p4_pt")
        with c2:
            tt = C.summary_table(t, "property_type", "Property type").sort_values("Median €/m²", ascending=False)
            C.show(C.bar(tt, "Property type", "Median €/m²", "Median rent by property type", horizontal=True, hover=["Listings"]), 380, "p4_pt2")
        st.dataframe(tt, hide_index=True, width="stretch")

    with tabs[3]:
        rows = []
        for col, label in AMENITIES.items():
            w, wo = df.loc[df[col] == True, "rent_per_sqm"], df.loc[df[col] == False, "rent_per_sqm"]  # noqa: E712
            rows.append({"Amenity": label, "With (n)": len(w), "Median with €/m²": w.median(), "Without (n)": len(wo),
                         "Median without €/m²": wo.median(), "Difference €/m²": (w.median() - wo.median()) if len(w) and len(wo) else None,
                         "Missing (n)": int(df[col].isna().sum())})
        am = pd.DataFrame(rows).round(2)
        long = am.melt(id_vars="Amenity", value_vars=["Median with €/m²", "Median without €/m²"], var_name="Group", value_name="Median €/m²")
        long["Group"] = long["Group"].str.replace(" €/m²", "")
        fig = C.bar(long, "Amenity", "Median €/m²", "Median rent with / without amenity", color="Group")
        fig.update_layout(barmode="group")
        fig.update_traces(textposition="none")
        C.show(fig, 340, "p4_amen")
        st.dataframe(am, hide_index=True, width="stretch")
        st.caption("Differences reflect who tends to have each feature (e.g. new buildings have lifts and balconies) – they are not the price effect of the feature.")

    with tabs[4]:
        n = df.assign(status=df["is_new_construction"].map({True: "Newly constructed", False: "Existing"}).fillna("Unknown"))
        c1, c2 = st.columns(2)
        with c1:
            C.show(C.box(n, "status", "rent_per_sqm", "Rent per m²: new vs existing"), 340, "p4_new")
        with c2:
            st.dataframe(C.summary_table(n, "status", "Status"), hide_index=True, width="stretch")

    with tabs[5]:
        listing_table(df.assign(snapshot=df["snapshot"].astype(pd.CategoricalDtype(T.SNAPSHOT_ORDER, ordered=True))), "p4", "letura_property_listings.csv")
