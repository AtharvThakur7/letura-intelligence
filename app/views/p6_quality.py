"""Page 6 – Data Quality & Pipeline Monitoring."""
from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import shared
from letura.analytics import repo, stats, transforms as T
from letura.db import DatabaseUnavailable, data_source_label
from letura.ui import components as C, theme

LIMITATIONS = [
    "Rental data are **historical asking rents** (Sep 2018 – Feb 2020), not current 2026 rents and not signed contracts.",
    "The four snapshots are **independent samples**; they are not the same properties followed over time.",
    "Advertised cold rent (Kaltmiete) and official Mietenspiegel reference rent are **different concepts** measured in different periods.",
    "Outliers are **flagged, never removed**: extreme values may be genuine luxury or special listings.",
    "The Wohnlagenverzeichnis is a **2025** classification; listings are matched only when street, house number range and odd/even numbering agree. 1,269 listings have no street/house number.",
    "The location extract holds **26,205** rows vs **25,786** stated in the PDF (+419). All rows are preserved; the cause is undetermined (likely duplicated range lines across page breaks).",
    "Construction year is missing for 508 listings; heating costs for 2,050; total rent for 364.",
    "No coordinates exist in the source, so no map is produced.",
    "Neighbourhood medians with fewer than 10 listings are unreliable and are flagged.",
]


def render() -> None:
    C.page_header("Data Quality & Pipeline Monitoring", "Source inventory, reconciliation, missing values, outliers and pipeline execution status.")
    try:
        dq = repo.load_table("analytics_data_quality")
    except (DatabaseUnavailable, Exception) as exc:  # noqa: BLE001
        st.error("Data-quality table unavailable. Run `python scripts/run_pipeline.py`.")
        st.caption(str(exc)[:200])
        return
    df = shared.load_listings_or_stop()
    t = theme.tokens(C.mode())

    st_counts = dq["status"].value_counts()
    miss = dq[dq.category == "missing_values"]
    crit_cols = ["baseRent", "livingSpace", "noRooms", "rent_per_sqm"]
    complete = 100 - miss[miss.column_name.isin(crit_cols)]["metric_pct"].fillna(0).max()
    C.kpi_row([
        ("Checks passed", f"{st_counts.get('pass', 0)} / {len(dq)}", f"{st_counts.get('warn', 0)} warnings · {st_counts.get('fail', 0)} failures"),
        ("Core-field completeness", f"{complete:.1f}%", "rent, area, rooms, rent/m²"),
        ("Records retained", f"{len(df):,}", "no records removed"),
        ("IQR outliers flagged", f"{int((df.outlier_iqr_global != 'normal').sum()):,}", "kept in all analyses"),
        ("Records with quality flags", f"{int(df.quality_flags.notna().sum()):,}", "suspicious values, kept"),
    ])
    if st_counts.get("fail", 0):
        C.banner(f"{st_counts['fail']} data-quality check(s) FAILED – see the reconciliation table.", "warn")

    tabs = st.tabs(["Reconciliation", "Missing values", "Duplicates & suspicious", "Outliers", "Coverage & locations", "Pipeline", "Limitations"])

    with tabs[0]:
        C.section("Raw → staging → analytics record counts")
        rc = dq[dq.category == "row_counts"][["object_name", "metric_value", "expected_value", "status", "details"]]
        rc = rc.rename(columns={"object_name": "Table", "metric_value": "Rows", "expected_value": "Expected", "status": "Status", "details": "Details"})
        st.dataframe(rc, hide_index=True, width="stretch")
        C.section("Reconciliation checks")
        rec = dq[dq.category == "reconciliation"][["check_name", "metric_value", "expected_value", "status", "details"]]
        st.dataframe(rec.rename(columns=str.title), hide_index=True, width="stretch")
        C.section("Snapshot-level record counts")
        snap = df.groupby("snapshot", observed=True).size().reset_index(name="Transformed").assign(snapshot=lambda d: d.snapshot.astype(str))
        snap["Expected"] = snap.snapshot.map(T.EXPECTED_SNAPSHOT_COUNTS)
        snap["Match"] = (snap.Transformed == snap.Expected).map({True: "✔", False: "✖"})
        st.dataframe(snap.rename(columns={"snapshot": "Snapshot"}), hide_index=True, width="stretch")
        C.download_csv(dq, "data_quality_checks.csv", "Download all checks (CSV)", key="p6_dl")

    with tabs[1]:
        m = miss.dropna(subset=["metric_pct"]).sort_values("metric_pct", ascending=False)
        m = m.assign(Column=m.column_name, **{"Missing %": m.metric_pct, "Missing rows": m.metric_value})
        C.show(C.bar(m, "Column", "Missing %", "Missing values by column (% of 3,759 Hamburg listings)", horizontal=True, text="Missing %"), max(380, 24 * len(m) + 80), "p6_miss")
        st.dataframe(m[["Column", "Missing rows", "Missing %", "status", "details"]], hide_index=True, width="stretch")
        st.caption("Missing tokens ('NA', empty, 'no_information') are converted to NULL; values are never imputed.")

    with tabs[2]:
        C.section("Duplicate checks")
        st.dataframe(dq[dq.category == "duplicates"][["check_name", "metric_value", "status", "details"]], hide_index=True, width="stretch")
        C.section("Invalid or suspicious values (flagged, not removed)")
        sus = dq[dq.category == "suspicious_values"][["check_name", "metric_value", "metric_pct", "status", "details"]]
        st.dataframe(sus, hide_index=True, width="stretch")
        flagged = df[df.quality_flags.notna()][["snapshot", "neighbourhood", "baseRent", "livingSpace", "noRooms", "rent_per_sqm", "yearConstructed", "quality_flags"]]
        flagged = flagged.assign(snapshot=flagged.snapshot.astype(str))
        with st.expander(f"Flagged records ({len(flagged)})"):
            st.dataframe(flagged, hide_index=True, width="stretch")
            C.download_csv(flagged, "flagged_records.csv", key="p6_flag")

    with tabs[3]:
        lo, hi = stats.iqr_bounds(df.rent_per_sqm)
        st.markdown(f"**1.5×IQR fences:** €{lo:.2f} – €{hi:.2f}/m². Records outside are flagged `high`/`low`; all remain in the dataset.")
        fig = C.hist(df, "rent_per_sqm", "Rent per m² with outlier fences", "€/m²", nbins=60, median=False)
        fig.add_vline(x=hi, line_dash="dot", line_color=t["bad"], annotation_text=f"Upper fence {hi:.2f}")
        C.show(fig, 340, "p6_out")
        o = df[df.outlier_iqr_global != "normal"]
        by = o.groupby(["snapshot", "outlier_iqr_global"], observed=True).size().reset_index(name="Records")
        by["snapshot"] = by.snapshot.astype(str)
        c1, c2 = st.columns(2)
        with c1:
            st.dataframe(by, hide_index=True, width="stretch")
        with c2:
            st.dataframe(o.nlargest(10, "rent_per_sqm")[["neighbourhood", "baseRent", "livingSpace", "rent_per_sqm"]], hide_index=True, width="stretch")
            st.caption("Ten highest rent/m² records – candidates for manual investigation.")

    with tabs[4]:
        C.section("Source data coverage")
        inv = pd.DataFrame([
            {"Source": "German rental listings (immo_data.csv)", "Table": "raw_rental_listings", "Period": "Sep 2018 – Feb 2020", "Used": "Hamburg subset → stg_hamburg_listings"},
            {"Source": "Hamburg Mietenspiegel 2025", "Table": "raw_mietenspiegel (+ metadata)", "Period": "Ref. date 1 Apr 2025", "Used": "fact_mietenspiegel_benchmarks"},
            {"Source": "Hamburg Wohnlagenverzeichnis 2025", "Table": "raw_residential_locations", "Period": "2025", "Used": "Address matching (optional)"},
        ])
        st.dataframe(inv, hide_index=True, width="stretch")
        lm = repo.load_table("analytics_location_matching")
        lm = lm[lm.snapshot == "All snapshots"]
        C.show(C.bar(lm, "match_status", "listing_count", "Wohnlage address-match outcome (listings)", text="listing_count", xlabel="Status", ylabel="Listings"), 320, "p6_loc")
        st.dataframe(dq[dq.category == "locations"][["check_name", "metric_value", "metric_pct", "details"]], hide_index=True, width="stretch")

    with tabs[5]:
        C.section("Pipeline execution status")
        try:
            runs = repo.load_pipeline_status()
        except Exception:  # noqa: BLE001
            runs = pd.DataFrame()
        if runs.empty:
            C.empty_state("No pipeline runs recorded yet. Run `python scripts/run_pipeline.py`.")
        else:
            last = runs.iloc[0]
            C.pills([(f"Last run: {last.status.upper()}", "good" if last.status == "success" else "warn"), (f"{last['finished_at']}", ""), (f"mode: {last['mode']}", "")])
            steps = pd.DataFrame(json.loads(last.steps_json))
            show = [c for c in ["step", "status", "seconds"] if c in steps]
            st.dataframe(steps[show], hide_index=True, width="stretch")
            st.dataframe(runs[["run_id", "started_at", "finished_at", "mode", "status"]], hide_index=True, width="stretch")
        st.caption(f"Data source: {data_source_label()}")

    with tabs[6]:
        for item in LIMITATIONS:
            st.markdown(f"- {item}")
