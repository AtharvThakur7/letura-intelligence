"""Idempotent builders for derived tables.

Safety model
------------
* Raw tables (raw_*) and the validated staging table are READ ONLY here.
* Derived tables are written to `<name>__build`, validated, then swapped in
  with an atomic RENAME TABLE. A failed build never leaves a half-written
  table in place.
* Only names with an allowed prefix can be replaced (see _assert_derived).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from letura.analytics import stats
from letura.analytics import transforms as T
from letura.db import APPROVED_OBJECTS, admin_engine, table_exists

log = logging.getLogger(__name__)

DERIVED_PREFIXES = ("int_", "analytics_", "v_ai_", "meta_", "fact_")
PROTECTED = {"raw_rental_listings", "raw_mietenspiegel", "raw_mietenspiegel_metadata",
             "raw_residential_locations", "stg_hamburg_listings"}

EXPECTED_SOURCE_COUNTS = {
    "raw_rental_listings": 268_850,
    "raw_mietenspiegel": 88,
    "raw_mietenspiegel_metadata": 1,
    "raw_residential_locations": 26_205,
    "stg_hamburg_listings": 3_759,
    "fact_mietenspiegel_benchmarks": 88,
}
PDF_STATED_LOCATION_COUNT = 25_786


def _assert_derived(name: str) -> None:
    if name in PROTECTED or not name.startswith(DERIVED_PREFIXES) or not re.fullmatch(r"[a-z0-9_]+", name):
        raise PermissionError(f"Refusing to replace non-derived object: {name}")


def swap_in(df: pd.DataFrame, name: str, engine: Engine, dtype=None, ddl_after: list[str] | None = None) -> int:
    """Write df to <name>__build, then atomically swap it in. Returns row count."""
    _assert_derived(name)
    build, old = f"{name}__build", f"{name}__old"
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS `{build}`"))
        conn.execute(text(f"DROP TABLE IF EXISTS `{old}`"))
    df.to_sql(build, engine, index=False, if_exists="fail", chunksize=1000, dtype=dtype)
    with engine.begin() as conn:
        for ddl in ddl_after or []:
            conn.execute(text(ddl.format(t=build)))
        n = conn.execute(text(f"SELECT COUNT(*) FROM `{build}`")).scalar()
        if n != len(df):
            raise RuntimeError(f"{name}: wrote {n} rows, expected {len(df)}")
    with engine.begin() as conn:
        if table_exists(name, engine):
            conn.execute(text(f"RENAME TABLE `{name}` TO `{old}`, `{build}` TO `{name}`"))
            conn.execute(text(f"DROP TABLE `{old}`"))
        else:
            conn.execute(text(f"RENAME TABLE `{build}` TO `{name}`"))
    return int(n)


# ==========================================================================
# 1. Mietenspiegel fact table (verify; rebuild only if missing)
# ==========================================================================
def build_fact_mietenspiegel_if_missing(engine: Engine) -> dict:
    if table_exists("fact_mietenspiegel_benchmarks", engine):
        n = int(pd.read_sql(text("SELECT COUNT(*) n FROM fact_mietenspiegel_benchmarks"), engine).n[0])
        return {"action": "verified_existing", "rows": n, "ok": n == 88}
    raw = pd.read_sql(text("SELECT * FROM raw_mietenspiegel"), engine)
    meta = pd.read_sql(text("SELECT * FROM raw_mietenspiegel_metadata"), engine).iloc[0]
    parts = raw["merkmale"].str.split("|", expand=True)
    df = pd.DataFrame({
        "source_id": raw["source_id"],
        "reference_rent_per_sqm": raw["mittelwert"].map(T.to_number),
        "minimum_rent_per_sqm": raw["spanne_min"].map(T.to_number),
        "maximum_rent_per_sqm": raw["spanne_max"].map(T.to_number),
        "underlying_record_count": raw["datensaetze"].map(T.to_number),
        "construction_period": parts[0], "equipment": parts[1],
        "residential_location": parts[2], "living_area_category": parts[3],
        "original_characteristics": raw["merkmale"],
        "coordinate_reference_system": raw["coordinate_reference_system"],
        "reference_date": meta["erhebungsstand"], "publisher": meta["herausgeber"],
        "source_note": meta["hinweis"], "source_title": meta["titel"],
        "characteristic_definitions": meta["merkmaletext"],
    })
    n = swap_in(df, "fact_mietenspiegel_benchmarks", engine)
    return {"action": "rebuilt_from_raw", "rows": n, "ok": n == 88}


# ==========================================================================
# 2. Intermediate enriched listings (int_hamburg_listings)
# ==========================================================================
STG_COLUMNS = [
    "source_record_id", "scoutId", "regio1", "regio2", "regio3", "geo_plz", "street", "streetPlain",
    "houseNumber", "date", "listing_date", "baseRent", "totalRent", "serviceCharge", "heatingCosts",
    "livingSpace", "noRooms", "rent_per_sqm", "yearConstructed", "typeOfFlat", "balcony", "garden", "lift",
    "hasKitchen", "newlyConst", "cellar", "condition", "interiorQual", "heatingType", "floor",
    "numberOfFloors", "petsAllowed", "energyEfficiencyClass", "lastRefurbish",
]
BOOL_COLS = {"balcony": "has_balcony", "garden": "has_garden", "lift": "has_lift", "hasKitchen": "has_kitchen",
             "newlyConst": "is_new_construction", "cellar": "has_cellar"}


def enrich_listings(stg: pd.DataFrame, locations: pd.DataFrame | None) -> pd.DataFrame:
    """Pure function: staging rows in -> enriched rows out (same row count, same order)."""
    df = stg.copy()
    n_in = len(df)
    df["listing_date"] = pd.to_datetime(df["listing_date"]).dt.date
    df["snapshot"] = df["listing_date"].map(T.snapshot_label)
    df["neighbourhood"] = df["regio3"].map(T.neighbourhood_name)
    df["bezirk"] = df["neighbourhood"].map(T.bezirk_for)
    df["property_type"] = df["typeOfFlat"].map(lambda v: None if T.is_missing(v) else str(v))
    for src, dst in BOOL_COLS.items():
        df[dst] = df[src].map(T.to_bool)
    for c in ["baseRent", "totalRent", "serviceCharge", "heatingCosts", "livingSpace", "noRooms", "rent_per_sqm"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["yearConstructed"] = pd.to_numeric(df["yearConstructed"], errors="coerce")
    # Recompute rent/m² independently and compare to staging (reconciliation, not replacement).
    df["rent_per_sqm_check"] = [T.rent_per_sqm(b, l) for b, l in zip(df["baseRent"], df["livingSpace"])]
    df["total_rent_per_sqm"] = np.where(df["livingSpace"] > 0, (df["totalRent"] / df["livingSpace"]).round(2), np.nan)
    df["size_band"] = df["livingSpace"].map(T.size_band)
    df["room_band"] = df["noRooms"].map(T.room_band)
    df["year_band"] = df["yearConstructed"].map(T.year_band)
    df["street_decoded"] = df["street"].map(T.decode_street)

    # ---- quality / outlier flags (never remove rows) ----
    df["outlier_iqr_global"] = stats.flag_outliers(df["rent_per_sqm"])
    df["outlier_iqr_snapshot"] = None
    for _, idx in df.groupby("snapshot").groups.items():
        df.loc[idx, "outlier_iqr_snapshot"] = stats.flag_outliers(df.loc[idx, "rent_per_sqm"])
    flags = []
    for r in df.itertuples(index=False):
        f = []
        if r.rent_per_sqm is not None and r.rent_per_sqm == r.rent_per_sqm:
            if r.rent_per_sqm < 5:
                f.append("rent_sqm_below_5")
            if r.rent_per_sqm > 40:
                f.append("rent_sqm_above_40")
        if r.livingSpace == r.livingSpace and r.livingSpace < 15:
            f.append("living_space_below_15")
        if r.yearConstructed == r.yearConstructed and not (T.MIN_PLAUSIBLE_YEAR <= r.yearConstructed <= T.MAX_PLAUSIBLE_YEAR + 1):
            f.append("implausible_construction_year")
        if r.totalRent == r.totalRent and r.totalRent < r.baseRent:
            f.append("total_rent_below_base_rent")
        if r.noRooms == r.noRooms and r.livingSpace == r.livingSpace and r.noRooms > 0 and r.livingSpace / r.noRooms < 8:
            f.append("area_per_room_below_8")
        flags.append(",".join(f) if f else None)
    df["quality_flags"] = flags
    df["is_flagged"] = df["quality_flags"].notna() | (df["outlier_iqr_global"] != "normal")

    # ---- optional Wohnlagen matching ----
    if locations is not None and not locations.empty:
        idx = T.LocationIndex(locations)
        res = [idx.match(s, h) for s, h in zip(df["street"], df["houseNumber"])]
        df["location_match_status"] = [m.status for m in res]
        df["location_class"] = [m.location_class for m in res]
        df["location_score"] = [m.location_score for m in res]
        df["location_candidates"] = [m.candidates for m in res]
    else:
        df["location_match_status"] = "not_run"
        df["location_class"] = None
        df["location_score"] = None
        df["location_candidates"] = 0

    # ---- Mietenspiegel characteristic mapping ----
    df["ms_construction_period"] = df["yearConstructed"].map(T.ms_construction_period)
    df["ms_residential_location"] = df["location_class"].map(lambda c: None if T.is_missing(c) else T.MS_LOCATIONS.get(c))
    df["ms_living_area_category"] = [T.ms_area_category(a, c) for a, c in zip(df["livingSpace"], df["location_class"])]

    if len(df) != n_in:
        raise RuntimeError("enrich_listings changed the row count – this must never happen")
    df["built_at"] = datetime.now().replace(microsecond=0)
    return df


def build_int_listings(engine: Engine, run_location_matching: bool = True) -> dict:
    stg = pd.read_sql(text("SELECT " + ", ".join(f"`{c}`" for c in STG_COLUMNS) + " FROM stg_hamburg_listings"), engine)
    locations = None
    if run_location_matching:
        locations = pd.read_sql(text(
            "SELECT location_id, street, house_number_start, house_number_end, numbering_type, "
            "location_class, location_score FROM raw_residential_locations"), engine)
    df = enrich_listings(stg, locations)
    n = swap_in(df, "int_hamburg_listings", engine, ddl_after=[
        "ALTER TABLE `{t}` ADD PRIMARY KEY (source_record_id)",
        "CREATE INDEX ix_snapshot ON `{t}` (snapshot(12))",
        "CREATE INDEX ix_nbh ON `{t}` (neighbourhood(40))",
    ])
    mismatch = int(((df["rent_per_sqm"] - pd.to_numeric(df["rent_per_sqm_check"])).abs() > 0.011).sum())
    return {"rows": n, "source_rows": len(stg), "rent_per_sqm_mismatches": mismatch,
            "location_status": df["location_match_status"].value_counts().to_dict()}


# ==========================================================================
# 3. Analytics tables
# ==========================================================================
def _with_all(df: pd.DataFrame, col: str = "snapshot") -> pd.DataFrame:
    a = df.copy()
    a[col] = "All snapshots"
    return pd.concat([df, a], ignore_index=True)


def _snap_order(s: str) -> int:
    return T.SNAPSHOT_ORDER.index(s) if s in T.SNAPSHOT_ORDER else 99


def analytics_rental_market(lst: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for snap, g in _with_all(lst).groupby("snapshot"):
        r = {"snapshot": snap, "snapshot_order": _snap_order(snap),
             "listing_date": g["listing_date"].iloc[0] if snap != "All snapshots" else None,
             "listing_count": len(g), "neighbourhood_count": g["neighbourhood"].nunique()}
        r.update(stats.describe(g["rent_per_sqm"], "rent_sqm_"))
        r.update({k: v for k, v in stats.describe(g["baseRent"], "base_rent_").items() if k.endswith(("median", "mean"))})
        r.update({k: v for k, v in stats.describe(g["livingSpace"], "living_space_").items() if k.endswith(("median", "mean"))})
        r.update({k: v for k, v in stats.describe(g["noRooms"], "rooms_").items() if k.endswith(("median", "mean"))})
        r["outlier_high_count"] = int((g["outlier_iqr_global"] == "high").sum())
        r["outlier_low_count"] = int((g["outlier_iqr_global"] == "low").sum())
        r["source"] = "int_hamburg_listings (ImmoScout24 historical asking rents)"
        rows.append(r)
    out = pd.DataFrame(rows).sort_values("snapshot_order").reset_index(drop=True)
    return out.drop(columns=["rent_sqm_n"])


def analytics_neighbourhoods(lst: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (snap, nbh), g in _with_all(lst).groupby(["snapshot", "neighbourhood"]):
        r = {"snapshot": snap, "snapshot_order": _snap_order(snap), "neighbourhood": nbh,
             "bezirk": g["bezirk"].iloc[0], "listing_count": len(g)}
        d = stats.describe(g["rent_per_sqm"], "rent_sqm_")
        d.pop("rent_sqm_n")
        r.update(d)
        r["median_living_space"] = stats.describe(g["livingSpace"])["median"]
        r["median_rooms"] = stats.describe(g["noRooms"])["median"]
        r["median_base_rent"] = stats.describe(g["baseRent"])["median"]
        r["share_location_gut"] = stats.pct((g["location_class"] == "gut").sum(), g["location_class"].notna().sum())
        r["location_matched_count"] = int(g["location_class"].notna().sum())
        r["sample_flag"] = stats.sample_flag(len(g))
        rows.append(r)
    out = pd.DataFrame(rows)
    # Rank within snapshot (only neighbourhoods with n >= 10 are ranked).
    out["rank_median_rent"] = None
    for snap, g in out.groupby("snapshot"):
        ok = g[g["listing_count"] >= stats.SMALL_SAMPLE_THRESHOLD].sort_values("rent_sqm_median", ascending=False)
        out.loc[ok.index, "rank_median_rent"] = range(1, len(ok) + 1)
    return out.sort_values(["snapshot_order", "rent_sqm_median"], ascending=[True, False]).reset_index(drop=True)


PROPERTY_DIMENSIONS = {
    "size_band": ("Living area band", T.SIZE_BAND_ORDER),
    "room_band": ("Room count", T.ROOM_BAND_ORDER),
    "year_band": ("Construction period", T.YEAR_BAND_ORDER),
    "property_type": ("Property type", None),
    "has_balcony": ("Balcony", None),
    "has_garden": ("Garden", None),
    "has_lift": ("Lift", None),
    "has_kitchen": ("Fitted kitchen", None),
    "is_new_construction": ("New construction", None),
    "has_cellar": ("Cellar", None),
    "location_class": ("Wohnlage (matched)", None),
    "bezirk": ("Bezirk (district)", None),
}


def _segment_label(v) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "Missing / unknown"
    if isinstance(v, (bool, np.bool_)):
        return "Yes" if v else "No"
    return str(v)


def analytics_property_insights(lst: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for snap, gs in _with_all(lst).groupby("snapshot"):
        total = len(gs)
        for dim, (label, order) in PROPERTY_DIMENSIONS.items():
            seg = gs[dim].map(_segment_label)
            coverage = stats.pct(gs[dim].notna().sum(), total)
            for val, g in gs.groupby(seg):
                r = {"snapshot": snap, "snapshot_order": _snap_order(snap), "dimension": dim,
                     "dimension_label": label, "segment": val,
                     "segment_order": (order.index(val) if order and val in order else 50 if val != "Missing / unknown" else 99),
                     "listing_count": len(g), "share_of_listings_pct": stats.pct(len(g), total),
                     "dimension_coverage_pct": coverage}
                d = stats.describe(g["rent_per_sqm"], "rent_sqm_")
                d.pop("rent_sqm_n")
                r.update(d)
                r["median_living_space"] = stats.describe(g["livingSpace"])["median"]
                r["sample_flag"] = stats.sample_flag(len(g))
                rows.append(r)
    return pd.DataFrame(rows).sort_values(["snapshot_order", "dimension", "segment_order", "segment"]).reset_index(drop=True)


def analytics_mietenspiegel_reference(fact: pd.DataFrame, lst: pd.DataFrame) -> pd.DataFrame:
    df = fact.copy()
    df["period_order"] = df["construction_period"].map(lambda p: T.MS_PERIODS.index(p) if p in T.MS_PERIODS else 99)
    df["area_order"] = df["living_area_category"].map(lambda a: T.MS_AREA_ORDER.index(a) if a in T.MS_AREA_ORDER else 99)
    df["range_width"] = (df["maximum_rent_per_sqm"] - df["minimum_rent_per_sqm"]).round(2)
    df["range_consistent"] = (df["minimum_rent_per_sqm"] <= df["reference_rent_per_sqm"]) & (
        df["reference_rent_per_sqm"] <= df["maximum_rent_per_sqm"])
    # Contextual: historical listings whose characteristics map to the same cell.
    m = lst.dropna(subset=["ms_construction_period", "ms_residential_location", "ms_living_area_category"])
    agg = []
    for key, g in m.groupby(["ms_construction_period", "ms_residential_location", "ms_living_area_category"]):
        d = stats.describe(g["rent_per_sqm"])
        agg.append({"construction_period": key[0], "residential_location": key[1], "living_area_category": key[2],
                    "hist_listing_count": d["n"], "hist_median_rent_sqm": d["median"],
                    "hist_p25_rent_sqm": d["p25"], "hist_p75_rent_sqm": d["p75"]})
    agg = pd.DataFrame(agg, columns=["construction_period", "residential_location", "living_area_category",
                                     "hist_listing_count", "hist_median_rent_sqm", "hist_p25_rent_sqm", "hist_p75_rent_sqm"])
    df = df.merge(agg, how="left", on=["construction_period", "residential_location", "living_area_category"])
    df["hist_listing_count"] = df["hist_listing_count"].fillna(0).astype(int)
    df["comparison_caveat"] = ("These datasets differ in reference period, population and methodology. This comparison "
                               "is contextual, not a same-period market premium or legal rent determination.")
    keep = ["source_id", "construction_period", "period_order", "equipment", "residential_location",
            "living_area_category", "area_order", "reference_rent_per_sqm", "minimum_rent_per_sqm",
            "maximum_rent_per_sqm", "range_width", "range_consistent", "underlying_record_count",
            "hist_listing_count", "hist_median_rent_sqm", "hist_p25_rent_sqm", "hist_p75_rent_sqm",
            "reference_date", "publisher", "source_title", "source_note", "comparison_caveat"]
    return df[keep].sort_values(["residential_location", "period_order", "area_order"]).reset_index(drop=True)


def analytics_location_matching(lst: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for snap, g in _with_all(lst).groupby("snapshot"):
        vc = g["location_match_status"].value_counts()
        for status, n in vc.items():
            rows.append({"snapshot": snap, "snapshot_order": _snap_order(snap), "match_status": status,
                         "listing_count": int(n), "share_pct": stats.pct(n, len(g))})
    return pd.DataFrame(rows).sort_values(["snapshot_order", "listing_count"], ascending=[True, False]).reset_index(drop=True)


# ==========================================================================
# 4. Data quality checks
# ==========================================================================
def _check(rows, category, check, obj, metric, status, details="", column=None, pct=None, expected=None):
    rows.append({"category": category, "check_name": check, "object_name": obj, "column_name": column,
                 "metric_value": None if metric is None else float(metric), "metric_pct": pct,
                 "expected_value": None if expected is None else float(expected),
                 "status": status, "details": details})


def analytics_data_quality(engine: Engine, lst: pd.DataFrame, fact: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    with engine.connect() as conn:
        # --- source inventory & expected counts
        for t, exp in EXPECTED_SOURCE_COUNTS.items():
            n = conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
            _check(rows, "row_counts", "expected_row_count", t, n, "pass" if n == exp else "fail",
                   f"expected {exp:,}, found {n:,}", expected=exp)
        raw_hh = conn.execute(text("SELECT COUNT(*) FROM raw_rental_listings WHERE LOWER(TRIM(regio1))='hamburg'")).scalar()
        raw_snap = dict(conn.execute(text(
            "SELECT `date`, COUNT(*) FROM raw_rental_listings WHERE LOWER(TRIM(regio1))='hamburg' GROUP BY `date`")).fetchall())
        raw_missing = conn.execute(text("""
            SELECT SUM(TRIM(yearConstructed) IN ('NA','')) yc, SUM(TRIM(totalRent) IN ('NA','')) tr,
                   SUM(TRIM(serviceCharge) IN ('NA','')) sc, SUM(TRIM(heatingCosts) IN ('NA','')) hc
            FROM raw_rental_listings WHERE LOWER(TRIM(regio1))='hamburg'""")).mappings().one()
        loc_dupes = conn.execute(text("""
            SELECT COUNT(*) FROM (SELECT street, house_number_start, house_number_end, numbering_type, COUNT(*) c
            FROM raw_residential_locations GROUP BY 1,2,3,4 HAVING c > 1) d""")).scalar()

    # --- reconciliation raw -> staging -> intermediate
    n = len(lst)
    _check(rows, "reconciliation", "raw_hamburg_to_staging", "stg_hamburg_listings", n,
           "pass" if raw_hh == n else "fail", f"raw Hamburg rows {raw_hh:,} vs transformed {n:,}", expected=raw_hh)
    for code, label in [("Sep18", "Sep 2018"), ("May19", "May 2019"), ("Oct19", "Oct 2019"), ("Feb20", "Feb 2020")]:
        got = int((lst["snapshot"] == label).sum())
        exp = T.EXPECTED_SNAPSHOT_COUNTS[label]
        _check(rows, "reconciliation", f"snapshot_count_{label}", "int_hamburg_listings", got,
               "pass" if got == exp == raw_snap.get(code) else "fail",
               f"raw {raw_snap.get(code)}, expected {exp}, transformed {got}", expected=exp)
    mism = int(((lst["rent_per_sqm"] - pd.to_numeric(lst["rent_per_sqm_check"])).abs() > 0.011).sum())
    _check(rows, "reconciliation", "rent_per_sqm_recalculation", "int_hamburg_listings", mism,
           "pass" if mism == 0 else "warn", "rows where baseRent/livingSpace differs from staged rent_per_sqm by > €0.01", expected=0)
    for col, key in [("yearConstructed", "yc"), ("totalRent", "tr"), ("serviceCharge", "sc"), ("heatingCosts", "hc")]:
        got = int(lst[col].isna().sum())
        _check(rows, "reconciliation", f"na_token_preserved_{col}", "int_hamburg_listings", got,
               "pass" if got == int(raw_missing[key]) else "fail",
               f"raw literal 'NA' count {int(raw_missing[key])} → NULL count {got}", column=col, expected=int(raw_missing[key]))

    # --- missingness profile
    for col in ["baseRent", "livingSpace", "noRooms", "rent_per_sqm", "totalRent", "serviceCharge", "heatingCosts",
                "yearConstructed", "property_type", "condition", "interiorQual", "heatingType", "street_decoded",
                "houseNumber", "energyEfficiencyClass", "lastRefurbish", "floor", "numberOfFloors", "petsAllowed"]:
        miss = int(lst[col].map(T.is_missing).sum())
        p = stats.pct(miss, n)
        crit = col in {"baseRent", "livingSpace", "noRooms", "rent_per_sqm"}
        status = "pass" if miss == 0 else ("fail" if crit else ("warn" if p and p > 20 else "info"))
        _check(rows, "missing_values", "missing_count", "int_hamburg_listings", miss, status,
               "NA / empty / no_information tokens treated as missing", column=col, pct=p)

    # --- duplicates
    d1 = int(lst["scoutId"].duplicated().sum())
    _check(rows, "duplicates", "duplicate_scout_id", "int_hamburg_listings", d1, "pass" if d1 == 0 else "warn",
           "duplicate listing IDs (scoutId)", expected=0)
    d2 = int(lst["source_record_id"].duplicated().sum())
    _check(rows, "duplicates", "duplicate_source_record_id", "int_hamburg_listings", d2, "pass" if d2 == 0 else "fail",
           "duplicate primary keys", expected=0)
    addr = lst[lst["street_decoded"].notna() & ~lst["houseNumber"].map(T.is_missing)]
    k = ["street_decoded", "houseNumber", "livingSpace", "baseRent"]
    d3 = int(addr.duplicated(subset=k + ["snapshot"]).sum())
    _check(rows, "duplicates", "possible_duplicate_within_snapshot", "int_hamburg_listings", d3, "info" if d3 else "pass",
           "same address + area + rent within one snapshot (kept; flagged for investigation)")
    d4 = int(addr.duplicated(subset=k).sum()) - d3
    _check(rows, "duplicates", "possible_relisting_across_snapshots", "int_hamburg_listings", max(d4, 0), "info",
           "same address + area + rent in a different snapshot (re-advertised units; kept)")
    _check(rows, "duplicates", "location_range_duplicates", "raw_residential_locations", loc_dupes, "info",
           "identical street + range + numbering type rows in the Wohnlagenverzeichnis extract")

    # --- invalid / suspicious values
    flag_counts: dict[str, int] = {}
    for f in lst["quality_flags"].dropna():
        for x in f.split(","):
            flag_counts[x] = flag_counts.get(x, 0) + 1
    for name, desc in [("rent_sqm_below_5", "rent/m² < €5"), ("rent_sqm_above_40", "rent/m² > €40"),
                       ("living_space_below_15", "living area < 15 m²"),
                       ("implausible_construction_year", f"construction year outside {T.MIN_PLAUSIBLE_YEAR}–{T.MAX_PLAUSIBLE_YEAR + 1}"),
                       ("total_rent_below_base_rent", "total rent lower than base rent"),
                       ("area_per_room_below_8", "less than 8 m² per room")]:
        c = flag_counts.get(name, 0)
        _check(rows, "suspicious_values", name, "int_hamburg_listings", c, "warn" if c else "pass",
               desc + " – flagged, not removed", pct=stats.pct(c, n))
    lo, hi = stats.iqr_bounds(lst["rent_per_sqm"])
    for side in ["high", "low"]:
        c = int((lst["outlier_iqr_global"] == side).sum())
        _check(rows, "outliers", f"iqr_outlier_{side}", "int_hamburg_listings", c, "info",
               f"1.5×IQR fences €{lo:.2f}–€{hi:.2f}/m²; records retained", column="rent_per_sqm", pct=stats.pct(c, n))

    # --- benchmark integrity
    bad = int((~((fact["minimum_rent_per_sqm"] <= fact["reference_rent_per_sqm"]) &
                 (fact["reference_rent_per_sqm"] <= fact["maximum_rent_per_sqm"]))).sum())
    _check(rows, "benchmark", "min_le_mean_le_max", "fact_mietenspiegel_benchmarks", bad, "pass" if bad == 0 else "fail",
           "every reference value lies within its official range", expected=0)
    nulls = int(fact[["reference_rent_per_sqm", "minimum_rent_per_sqm", "maximum_rent_per_sqm"]].isna().any(axis=1).sum())
    _check(rows, "benchmark", "missing_reference_values", "fact_mietenspiegel_benchmarks", nulls,
           "pass" if nulls == 0 else "fail", expected=0)
    combos = 10 * 4 + 10 * 5
    _check(rows, "benchmark", "characteristic_grid_coverage", "fact_mietenspiegel_benchmarks", len(fact), "info",
           f"{len(fact)} of {combos} possible period × location × area cells published (2 cells not published for 'Gute Wohnlage')",
           expected=combos)

    # --- location source
    _check(rows, "locations", "pdf_vs_loaded_count", "raw_residential_locations", EXPECTED_SOURCE_COUNTS["raw_residential_locations"],
           "info", f"loaded 26,205 vs PDF-stated {PDF_STATED_LOCATION_COUNT:,}: +419 extracted rows preserved (see docs)",
           expected=PDF_STATED_LOCATION_COUNT)
    vc = lst["location_match_status"].value_counts()
    for st_, c in vc.items():
        _check(rows, "locations", f"listing_match_{st_}", "int_hamburg_listings", int(c), "info",
               "conservative Wohnlagen address match result", pct=stats.pct(c, n))

    df = pd.DataFrame(rows)
    df.insert(0, "check_id", range(1, len(df) + 1))
    df["checked_at"] = datetime.now().replace(microsecond=0)
    return df


# ==========================================================================
# 5. Read-only AI view + account
# ==========================================================================
AI_VIEW_SQL = """
CREATE OR REPLACE SQL SECURITY DEFINER VIEW v_ai_listings AS
SELECT source_record_id, snapshot, listing_date, neighbourhood, bezirk, geo_plz, property_type,
       baseRent AS base_rent, totalRent AS total_rent, livingSpace AS living_space, noRooms AS rooms,
       rent_per_sqm, yearConstructed AS year_constructed, has_balcony, has_garden, has_lift, has_kitchen,
       is_new_construction, has_cellar, `condition`, interiorQual AS interior_quality, size_band, room_band,
       year_band, location_class, location_match_status, ms_construction_period, ms_living_area_category,
       outlier_iqr_global, quality_flags
FROM int_hamburg_listings
"""


def build_ai_view_and_grants(engine: Engine, ro_user: str, ro_password: str, db_name: str) -> dict:
    with engine.begin() as conn:
        conn.execute(text(AI_VIEW_SQL))
    if not ro_user or not ro_password:
        return {"view": "v_ai_listings", "readonly_user": "skipped (AI_DB_USER / AI_DB_PASSWORD not set)"}
    if not re.fullmatch(r"[A-Za-z0-9_]{1,32}", ro_user) or not re.fullmatch(r"[A-Za-z0-9_]+", db_name):
        raise ValueError("Invalid read-only user or database name")
    with engine.begin() as conn:
        exists = conn.execute(text("SELECT COUNT(*) FROM mysql.user WHERE user=:u AND host='localhost'"), {"u": ro_user}).scalar()
        if exists:
            conn.execute(text(f"ALTER USER '{ro_user}'@'localhost' IDENTIFIED BY :p"), {"p": ro_password})
        else:
            conn.execute(text(f"CREATE USER '{ro_user}'@'localhost' IDENTIFIED BY :p"), {"p": ro_password})
        # Reset to no privileges, then grant SELECT on approved objects only.
        conn.execute(text(f"REVOKE ALL PRIVILEGES, GRANT OPTION FROM '{ro_user}'@'localhost'"))
        granted = []
        for obj in APPROVED_OBJECTS:
            if table_exists(obj, engine):
                conn.execute(text(f"GRANT SELECT ON `{db_name}`.`{obj}` TO '{ro_user}'@'localhost'"))
                granted.append(obj)
        conn.execute(text(f"ALTER USER '{ro_user}'@'localhost' WITH MAX_USER_CONNECTIONS 10"))
    return {"view": "v_ai_listings", "readonly_user": ro_user, "granted_select_on": granted}


# ==========================================================================
# 6. Pipeline run log
# ==========================================================================
def log_pipeline_run(engine: Engine, run: dict) -> None:
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS meta_pipeline_runs (
                run_id VARCHAR(40) PRIMARY KEY, started_at DATETIME, finished_at DATETIME,
                mode VARCHAR(20), status VARCHAR(20), steps_json LONGTEXT, message TEXT)"""))
        conn.execute(text("""INSERT INTO meta_pipeline_runs VALUES (:run_id, :started_at, :finished_at, :mode,
                             :status, :steps_json, :message)"""),
                     {**run, "steps_json": json.dumps(run["steps"], default=str)[:1_000_000]})
