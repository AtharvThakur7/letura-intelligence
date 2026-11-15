"""Properties: how rent relates to size, age, type and features, plus a searchable listing table."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app import shared
from app.views.p2_explorer import listing_table
from letura.analytics import stats, transforms as T
from letura.analytics.filters import AMENITIES
from letura.ui import components as C


def _ordered(tbl: pd.DataFrame, col: str, order: list[str]) -> pd.DataFrame:
    return tbl.assign(_o=tbl[col].map(lambda v: order.index(v) if v in order else 99)).sort_values("_o").drop(columns="_o")


def render() -> None:
    C.page_header("Properties", "How rent per m² differs by size, age, type and features, and the listings behind it.")
    df_all = shared.load_listings_or_stop()
    f = shared.current_filters(df_all)
    df = shared.filtered(df_all, f)
    if df.empty:
        C.empty_state()
        return
    df = df.assign(snapshot=df["snapshot"].astype(str))

    tab_size, tab_age, tab_type, tab_list = st.tabs(["Size & rooms", "Building age", "Type & features", "Browse listings"])

    with tab_size:
        c1, c2 = st.columns(2)
        with c1:
            C.show(C.scatter(df, "livingSpace", "rent_per_sqm", "Rent per m² vs flat size", xlabel="Size (m²)", ylabel="€/m²",
                             hover=["neighbourhood", "snapshot"], trend=True), 360, "p4_s1")
        with c2:
            C.show(C.box(df, "room_band", "rent_per_sqm", "Rent per m² by rooms", order=T.ROOM_BAND_ORDER, xlabel="Rooms"), 360, "p4_rb")
        sub = df.dropna(subset=["livingSpace", "rent_per_sqm"])
        if len(sub) > 10:
            rho = stats.spearman(sub["livingSpace"], sub["rent_per_sqm"])
            st.caption(f"Rank correlation between size and rent per m²: {rho:.2f} (0 = no pattern). Differences shown are associations, not causes.")
        with st.expander("Numbers by size band"):
            st.dataframe(_ordered(C.summary_table(df, "size_band", "Size"), "Size", T.SIZE_BAND_ORDER), hide_index=True, width="stretch")

    with tab_age:
        y = df.dropna(subset=["yearConstructed"])
        y = y[(y["yearConstructed"] >= T.MIN_PLAUSIBLE_YEAR) & (y["yearConstructed"] <= T.MAX_PLAUSIBLE_YEAR + 1)]
        if len(y) < 5:
            C.empty_state("Not enough listings with a year built in this selection.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                C.show(C.scatter(y, "yearConstructed", "rent_per_sqm", "Rent per m² by year built", xlabel="Year built", ylabel="€/m²",
                                 hover=["neighbourhood", "snapshot"], trend=True), 360, "p4_year")
            with c2:
                C.show(C.box(y, "year_band", "rent_per_sqm", "Rent per m² by period built", order=T.YEAR_BAND_ORDER), 360, "p4_yb")
            st.caption(f"{len(df) - len(y):,} listings have no usable year built and are not shown here.")

    with tab_type:
        t = df.assign(property_type=df["property_type"].fillna("Not stated"))
        order = t.groupby("property_type")["rent_per_sqm"].median().sort_values(ascending=False).index.tolist()
        c1, c2 = st.columns(2)
        with c1:
            C.show(C.box(t, "property_type", "rent_per_sqm", "Rent per m² by property type", order=order), 360, "p4_pt")
        with c2:
            rows = []
            for col, label in AMENITIES.items():
                for val, name in [(True, "With"), (False, "Without")]:
                    s = df.loc[df[col] == val, "rent_per_sqm"]
                    rows.append({"Feature": label, "Group": name, "Median €/m²": s.median() if len(s) else None, "Listings": len(s)})
            am = pd.DataFrame(rows).dropna(subset=["Median €/m²"]).round(2)
            fig = C.bar(am, "Feature", "Median €/m²", "Median rent with / without each feature", color="Group", hover=["Listings"])
            fig.update_layout(barmode="group")
            fig.update_traces(textposition="none")
            C.show(fig, 360, "p4_amen")
        st.caption("Flats with a lift or balcony are often newer or bigger, so these gaps are not the price effect of the feature itself.")

    with tab_list:
        listing_table(df.assign(snapshot=df["snapshot"].astype(pd.CategoricalDtype(T.SNAPSHOT_ORDER, ordered=True))), "p4", "letura_listings.csv")
