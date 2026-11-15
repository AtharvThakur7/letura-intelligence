"""Page 5 – Mietenspiegel Benchmark (official 2025 reference rents vs historical listings)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import shared
from letura.analytics import repo, stats, transforms as T
from letura.ui import components as C, theme


def render() -> None:
    C.page_header("Mietenspiegel Benchmark", "Official Hamburg Mietenspiegel 2025 reference rents, shown alongside – never merged with – historical advertised rents.")
    try:
        ref = repo.load_table("analytics_mietenspiegel_reference")
    except Exception as exc:  # noqa: BLE001
        st.error("Mietenspiegel analytics table unavailable. Run `python scripts/run_pipeline.py`.")
        st.caption(str(exc)[:200])
        return
    df_all = shared.load_listings_or_stop()
    t = theme.tokens(C.mode())

    r0 = ref.iloc[0]
    C.banner(C.BENCHMARK_CAVEAT)
    C.pills([(f"Reference date: {pd.to_datetime(r0['reference_date']):%d %b %Y}", "accent"), ("Official reference rents (not asking rents)", ""),
             ("Net cold rent, excl. heating & operating costs", ""), (f"{len(ref)} published cells", "")])
    with st.expander("Source & definitions"):
        st.markdown(f"**Publisher:** {r0['publisher']}  \n**Title:** {r0['source_title']}  \n**Reference date:** {pd.to_datetime(r0['reference_date']):%d.%m.%Y}")
        st.markdown(f"**Official note (German, verbatim):** {r0['source_note']}")
        st.caption("All 88 cells share the equipment class 'mit Bad und Sammelheizung'. Reference rent = mean (Mittelwert); range = published Spanne (min–max).")

    C.section("Select benchmark characteristics")
    c1, c2, c3, c4 = st.columns(4)
    loc = c1.selectbox("Residential location", sorted(ref["residential_location"].unique()))
    sub_loc = ref[ref["residential_location"] == loc]
    areas = sorted(sub_loc["living_area_category"].unique(), key=lambda a: T.MS_AREA_ORDER.index(a) if a in T.MS_AREA_ORDER else 99)
    area = c2.selectbox("Living-area category", areas)
    period = c3.selectbox("Construction period", T.MS_PERIODS, index=6)
    c4.selectbox("Equipment", sorted(ref["equipment"].unique()), disabled=True, help="Only one equipment class is published.")

    sel = ref[(ref.residential_location == loc) & (ref.living_area_category == area) & (ref.construction_period == period)]
    if sel.empty:
        C.empty_state("The Mietenspiegel does not publish a value for this combination (e.g. 'ab 131m²' × 1961–1967 in a Gute Wohnlage). No value is estimated.")
    else:
        s = sel.iloc[0]
        C.kpi_row([
            ("Reference rent (mean)", C.eur_sqm(s.reference_rent_per_sqm), "official Mittelwert"),
            ("Minimum", C.eur_sqm(s.minimum_rent_per_sqm), "lower end of published range"),
            ("Maximum", C.eur_sqm(s.maximum_rent_per_sqm), "upper end of published range"),
            ("Range width", C.eur_sqm(s.range_width), f"{s.underlying_record_count:.0f} source records" if pd.notna(s.underlying_record_count) else "source record count not published"),
        ])
        # Historical listings with matching characteristics (contextual only)
        hist = df_all[(df_all.ms_construction_period == period) & (df_all.ms_residential_location == loc) & (df_all.ms_living_area_category == area)]
        st.markdown(f"**Historical listings mapped to the same characteristics (2018–2020, contextual):** {len(hist)}")
        if len(hist) >= 5:
            d = stats.describe(hist["rent_per_sqm"])
            C.kpi_row([("Historical median", C.eur_sqm(d["median"]), f"n={d['n']} · P25–P75 €{d['p25']:.2f}–€{d['p75']:.2f}"),
                       ("Historical mean", C.eur_sqm(d["mean"]), "advertised, cold"),
                       ("Difference of medians", f"{d['median'] - s.reference_rent_per_sqm:+.2f} €/m²", "contextual – different periods & methods")])
            fig = go.Figure()
            fig.add_trace(go.Box(y=hist["rent_per_sqm"], name="Historical asking rents 2018–20", boxpoints="all", jitter=.4, pointpos=0,
                                 marker=dict(color=t["series"][1], size=5, opacity=.6), line=dict(color=t["series"][1])))
            fig.add_hrect(y0=s.minimum_rent_per_sqm, y1=s.maximum_rent_per_sqm, fillcolor=t["series"][0], opacity=.15, line_width=0,
                          annotation_text="Mietenspiegel 2025 range", annotation_position="top left", annotation_font_color=t["text2"])
            fig.add_hline(y=s.reference_rent_per_sqm, line_color=t["series"][0], line_width=2,
                          annotation_text=f"Reference €{s.reference_rent_per_sqm:.2f}", annotation_font_color=t["text2"])
            fig.update_layout(yaxis_title="€/m²", showlegend=False)
            C.show(fig, 360, "p5_cmp")
        else:
            C.empty_state(f"Only {len(hist)} historical listings map to this combination (Wohnlage requires a matched address and construction year). "
                          "No comparison is drawn from so few observations.")

    C.section("Benchmark range comparison", "Official reference mean with min–max range for the selected location and living-area category.")
    rng = sub_loc[sub_loc.living_area_category == area].sort_values("period_order")
    if rng.empty:
        C.empty_state()
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rng.construction_period, y=rng.maximum_rent_per_sqm, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=rng.construction_period, y=rng.minimum_rent_per_sqm, mode="lines", line=dict(width=0), fill="tonexty",
                                 fillcolor="rgba(57,135,229,.18)", name="Published range (min–max)", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=rng.construction_period, y=rng.reference_rent_per_sqm, mode="lines+markers", name="Reference rent (mean)",
                                 line=dict(color=t["series"][0], width=2.5), marker=dict(size=9, line=dict(color=t["surface"], width=2)),
                                 customdata=rng[["minimum_rent_per_sqm", "maximum_rent_per_sqm"]],
                                 hovertemplate="%{x}<br>Reference €%{y:.2f}/m²<br>Range €%{customdata[0]:.2f}–€%{customdata[1]:.2f}<extra></extra>"))
        if len(sel):
            fig.add_trace(go.Scatter(x=[period], y=[sel.iloc[0].reference_rent_per_sqm], mode="markers", name="Selected",
                                     marker=dict(size=15, symbol="diamond", color="rgba(0,0,0,0)", line=dict(color=t["text"], width=2))))
        fig.update_layout(title=f"{loc} · {area}", yaxis_title="€/m² (net cold)", xaxis_title="Construction period")
        C.show(fig, 380, "p5_range")

    c1, c2 = st.columns(2)
    with c1:
        C.section("Reference rent by period × area")
        piv = sub_loc.pivot_table(index="living_area_category", columns="construction_period", values="reference_rent_per_sqm")
        piv = piv.reindex(index=[a for a in T.MS_AREA_ORDER if a in piv.index], columns=[p for p in T.MS_PERIODS if p in piv.columns])
        fig = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index, colorscale=[[0, t["seq"][0]], [1, t["seq"][-1]]] if C.mode() == "light" else [[0, t["seq"][0]], [1, t["seq"][-1]]],
                                   hovertemplate="%{y}<br>%{x}<br>€%{z:.2f}/m²<extra></extra>", colorbar=dict(title="€/m²"),
                                   text=piv.round(2).values, texttemplate="%{text}", textfont=dict(size=10)))
        fig.update_layout(title=loc, xaxis=dict(tickangle=-40))
        C.show(fig, 400, "p5_heat")
    with c2:
        C.section("Normal vs good residential location")
        both = ref.groupby(["residential_location", "construction_period"], as_index=False)["reference_rent_per_sqm"].median()
        both["o"] = both.construction_period.map(T.MS_PERIODS.index)
        both = both.sort_values("o")
        fig = C.line(both, "construction_period", "reference_rent_per_sqm", "Median reference rent across area categories", color="residential_location", ylabel="€/m²", order=T.MS_PERIODS)
        fig.update_xaxes(tickangle=-40)
        C.show(fig, 400, "p5_nvg")
        st.caption("Median across the published living-area categories in each period (good-location cells include two additional size classes).")

    C.section("Historical listings vs Mietenspiegel by construction period", "Listings are mapped by construction year to the nearest published period; unmappable years (e.g. 1948) are excluded.")
    h = df_all.dropna(subset=["ms_construction_period"])
    g = h.groupby("ms_construction_period").agg(hist_median=("rent_per_sqm", "median"), n=("rent_per_sqm", "size")).reset_index()
    refp = ref.groupby("construction_period")["reference_rent_per_sqm"].median().reset_index()
    m = g.merge(refp, left_on="ms_construction_period", right_on="construction_period", how="outer")
    m["period"] = m["ms_construction_period"].fillna(m["construction_period"])
    m["o"] = m.period.map(T.MS_PERIODS.index)
    m = m.sort_values("o")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=m.period, y=m.hist_median, name="Historical asking rent median (2018–20)", marker_color=t["series"][1], customdata=m.n,
                         hovertemplate="%{x}<br>Median €%{y:.2f}/m²<br>n=%{customdata}<extra></extra>"))
    fig.add_trace(go.Bar(x=m.period, y=m.reference_rent_per_sqm, name="Mietenspiegel 2025 median reference", marker_color=t["series"][0]))
    fig.update_layout(barmode="group", yaxis_title="€/m²", xaxis_tickangle=-30)
    C.show(fig, 380, "p5_period")
    out = m[["period", "n", "hist_median", "reference_rent_per_sqm"]].rename(columns={"period": "Construction period", "n": "Historical listings", "hist_median": "Historical median €/m²", "reference_rent_per_sqm": "Reference median €/m² (all cells)"}).round(2)
    st.dataframe(out, hide_index=True, width="stretch")
    C.banner(C.BENCHMARK_CAVEAT)

    C.section("Full benchmark table")
    cols = ["residential_location", "construction_period", "living_area_category", "equipment", "reference_rent_per_sqm", "minimum_rent_per_sqm", "maximum_rent_per_sqm",
            "hist_listing_count", "hist_median_rent_sqm"]
    tbl = ref[cols].rename(columns={"residential_location": "Location", "construction_period": "Construction period", "living_area_category": "Living area",
                                    "equipment": "Equipment", "reference_rent_per_sqm": "Reference €/m²", "minimum_rent_per_sqm": "Min €/m²",
                                    "maximum_rent_per_sqm": "Max €/m²", "hist_listing_count": "Hist. listings (n)", "hist_median_rent_sqm": "Hist. median €/m²"})
    st.dataframe(tbl, hide_index=True, width="stretch", height=360)
    C.download_csv(tbl, "mietenspiegel_2025_benchmarks.csv", key="p5_dl")
