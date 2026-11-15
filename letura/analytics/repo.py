"""Data access for the dashboard. All metrics originate from MySQL.

Loaders are cached by Streamlit when running inside the app (see ``cached``),
and fall back to plain functions in tests/pipeline.
"""
from __future__ import annotations

import pandas as pd

from letura.analytics import transforms as T
from letura.db import read_df

LISTING_COLUMNS = [
    "source_record_id", "scoutId", "snapshot", "listing_date", "neighbourhood", "bezirk", "geo_plz",
    "street_decoded", "houseNumber", "property_type", "baseRent", "totalRent", "serviceCharge",
    "livingSpace", "noRooms", "rent_per_sqm", "yearConstructed", "has_balcony", "has_garden", "has_lift",
    "has_kitchen", "is_new_construction", "has_cellar", "condition", "interiorQual", "size_band",
    "room_band", "year_band", "outlier_iqr_global", "outlier_iqr_snapshot", "quality_flags", "is_flagged",
    "location_class", "location_score", "location_match_status", "ms_construction_period",
    "ms_residential_location", "ms_living_area_category",
]
BOOL_COLUMNS = ["has_balcony", "has_garden", "has_lift", "has_kitchen", "is_new_construction", "has_cellar"]


def cached(ttl: int = 600):
    """Use st.cache_data inside Streamlit, identity elsewhere."""
    def deco(fn):
        try:
            import streamlit as st
            return st.cache_data(ttl=ttl, show_spinner=False)(fn)
        except Exception:  # noqa: BLE001
            return fn
    return deco


@cached()
def load_listings() -> pd.DataFrame:
    df = read_df("SELECT " + ", ".join(f"`{c}`" for c in LISTING_COLUMNS) + " FROM int_hamburg_listings")
    for c in BOOL_COLUMNS:
        df[c] = df[c].map({1: True, 0: False})
    df["snapshot"] = pd.Categorical(df["snapshot"], categories=T.SNAPSHOT_ORDER, ordered=True)
    df["listing_date"] = pd.to_datetime(df["listing_date"])
    return df


@cached()
def load_table(name: str) -> pd.DataFrame:
    allowed = {"analytics_hamburg_rental_market", "analytics_hamburg_neighbourhoods",
               "analytics_hamburg_property_insights", "analytics_mietenspiegel_reference",
               "analytics_data_quality", "analytics_location_matching", "meta_pipeline_runs",
               "fact_mietenspiegel_benchmarks"}
    if name not in allowed:
        raise ValueError(f"table not approved: {name}")
    return read_df(f"SELECT * FROM `{name}`")


@cached(ttl=60)
def load_pipeline_status() -> pd.DataFrame:
    return read_df("SELECT run_id, started_at, finished_at, mode, status, steps_json FROM meta_pipeline_runs "
                   "ORDER BY started_at DESC LIMIT 10")


def health_check() -> tuple[bool, str]:
    try:
        n = read_df("SELECT COUNT(*) n FROM int_hamburg_listings").n[0]
        return (n > 0, f"{n:,} listings available") if n else (False, "int_hamburg_listings is empty – run the pipeline")
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
