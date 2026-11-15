"""Shared app plumbing: theme, sidebar filters, data loading with friendly errors."""
from __future__ import annotations

import streamlit as st

from letura import APP_NAME, APP_SUBTITLE
from letura.analytics import repo, transforms as T
from letura.analytics.filters import AMENITIES, FilterState, apply_filters
from letura.db import DatabaseUnavailable
from letura.ui import theme

AREA_MAX = 250.0
FILTER_KEYS = ["f_snap", "f_nbh", "f_type", "f_rooms", "f_area", "f_year", "f_amen"]


def init_theme() -> None:
    if "theme_mode" not in st.session_state:
        try:
            st.session_state.theme_mode = "dark" if st.context.theme.type == "dark" else "light"
        except Exception:  # noqa: BLE001
            st.session_state.theme_mode = "light"
    st.markdown(theme.css(st.session_state.theme_mode), unsafe_allow_html=True)


def load_listings_or_stop():
    """Load listings; on failure show a helpful message instead of a stack trace."""
    try:
        df = repo.load_listings()
    except DatabaseUnavailable as exc:
        st.error(f"Database unavailable. {exc}")
        st.info("Start MySQL, check `.env`, then run `python scripts/run_pipeline.py`.")
        st.stop()
    except Exception as exc:  # noqa: BLE001
        st.error("Could not load listings. Has the pipeline been run? (`python scripts/run_pipeline.py`)")
        st.caption(f"{type(exc).__name__}: {str(exc)[:200]}")
        st.stop()
    return df


def reset_filters() -> None:
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def sidebar_brand() -> None:
    st.sidebar.markdown(
        f'<div class="lt-brand"><div class="lt-logo">L</div><div><b>{APP_NAME}</b><small>{APP_SUBTITLE}</small></div></div>',
        unsafe_allow_html=True)


def sidebar_theme_toggle() -> None:
    dark = st.sidebar.toggle("Dark mode", value=st.session_state.get("theme_mode") == "dark", key="dark_toggle")
    new = "dark" if dark else "light"
    if new != st.session_state.get("theme_mode"):
        st.session_state.theme_mode = new
        st.rerun()


def sidebar_filters(df) -> FilterState:
    with st.sidebar.expander("Filters", expanded=True):
        st.caption("Apply to Pages 1–4 and the AI analyst.")
        st.multiselect("Snapshot", T.SNAPSHOT_ORDER, key="f_snap")
        nbh = sorted(df["neighbourhood"].dropna().unique())
        st.multiselect("Neighbourhood", nbh, key="f_nbh")
        st.multiselect("Property type", sorted(df["property_type"].dropna().unique()), key="f_type")
        st.multiselect("Rooms", T.ROOM_BAND_ORDER, key="f_rooms")
        hi = float(df["livingSpace"].max())
        st.slider("Living area (m²)", 0.0, AREA_MAX, (0.0, AREA_MAX), step=1.0, key="f_area",
                  help=f"Slider capped at {AREA_MAX:.0f} m²; the largest listing is {hi:.0f} m² (use 250 to include all).")
        st.slider("Construction year", 1850, 2020, (1850, 2020), key="f_year",
                  help="Applies only to listings with a construction year; the rest are excluded when this is narrowed.")
        st.multiselect("Amenities (all selected)", list(AMENITIES), format_func=AMENITIES.get, key="f_amen")
        st.button("Reset filters", on_click=reset_filters, width="stretch")
    return current_filters(df)


def current_filters(df=None) -> FilterState:
    ss = st.session_state
    area = ss.get("f_area")
    year = ss.get("f_year")
    return FilterState(
        snapshots=list(ss.get("f_snap", [])), neighbourhoods=list(ss.get("f_nbh", [])),
        property_types=list(ss.get("f_type", [])), rooms=list(ss.get("f_rooms", [])),
        area_range=tuple(area) if area and tuple(area) != (0.0, AREA_MAX) else None,
        year_range=tuple(year) if year and tuple(year) != (1850, 2020) else None,
        amenities=list(ss.get("f_amen", [])),
    )


def filtered(df, f: FilterState):
    out = apply_filters(df, f)
    st.caption(f"**{len(out):,}** of {len(df):,} listings · {f.describe()}")
    return out
