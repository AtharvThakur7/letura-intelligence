"""Shared app plumbing: theme, sidebar filters, data loading with friendly errors."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from letura import APP_NAME, APP_SUBTITLE
from letura.analytics import repo, transforms as T
from letura.analytics.filters import AMENITIES, FilterState, apply_filters
from letura.db import DatabaseUnavailable
from letura.i18n import LANGUAGES, lang, set_lang, t
from letura.ui import theme

AREA_MAX = 250.0
FILTER_KEYS = ["f_snap", "f_nbh", "f_type", "f_rooms", "f_area", "f_year", "f_amen"]


def init_theme() -> None:
    # Light is the product default regardless of the visitor's OS/browser theme; dark only once the
    # user explicitly flips the sidebar toggle (sidebar_theme_toggle persists that choice for the session).
    st.session_state.setdefault("theme_mode", "light")
    st.markdown(theme.css(st.session_state.theme_mode), unsafe_allow_html=True)


def init_language() -> None:
    if "lang" not in st.session_state:
        st.session_state.lang = "en"


DROPDOWN_FIX_JS = """
<script>
(function () {
  const w = window.parent; const d = w.document;
  if (w.__ltDropdownFix2) return; w.__ltDropdownFix2 = true;
  // Streamlit 1.67 dropdowns re-open when the arrow is clicked while open. Make the arrow a real toggle:
  // remember whether the list was open when the press STARTED, then swallow the press and close it.
  const SEL = '[data-testid="stMultiSelect"] button[aria-haspopup="listbox"], [data-testid="stSelectbox"] button[aria-haspopup="listbox"]';
  const arrow = el => el && el.closest ? el.closest(SEL) : null;
  let wasOpen = false, target = null;
  const stop = e => { e.stopImmediatePropagation(); e.preventDefault(); };
  d.addEventListener('pointerdown', e => {
    const b = arrow(e.target); target = b;
    wasOpen = !!(b && b.getAttribute('aria-expanded') === 'true');
    if (wasOpen) stop(e);
  }, true);
  ['mousedown', 'pointerup', 'mouseup'].forEach(type => d.addEventListener(type, e => { if (wasOpen && arrow(e.target)) stop(e); }, true));
  d.addEventListener('click', e => {
    if (!(wasOpen && arrow(e.target))) return;
    stop(e);
    const root = target.closest('[data-testid="stMultiSelect"], [data-testid="stSelectbox"]');
    const input = root && root.querySelector('input');
    if (input) { input.focus(); input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true})); }
    wasOpen = false;
  }, true);
})();
</script>
"""


def inject_dropdown_fix() -> None:
    """Zero-height helper so clicking a dropdown's arrow again closes it."""
    components.html(DROPDOWN_FIX_JS, height=0)


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
    """Reset every filter widget to its default VALUE. (Deleting the keys instead leaves stale tags on screen.)"""
    ss = st.session_state
    ss["f_snap"], ss["f_nbh"], ss["f_type"], ss["f_rooms"], ss["f_amen"] = [], [], [], [], []
    ss["f_area"] = (0.0, AREA_MAX)
    ss["f_year"] = (1850, 2020)


def sidebar_brand() -> None:
    st.sidebar.markdown(
        f'<div class="lt-brand"><div class="lt-logo">L</div><div><b>{APP_NAME}</b><small>{APP_SUBTITLE}</small></div></div>',
        unsafe_allow_html=True)


def sidebar_theme_toggle() -> None:
    dark = st.sidebar.toggle(t("Dark mode"), value=st.session_state.get("theme_mode") == "dark", key="dark_toggle")
    new = "dark" if dark else "light"
    if new != st.session_state.get("theme_mode"):
        st.session_state.theme_mode = new
        st.rerun()


def sidebar_language_toggle() -> None:
    codes = list(LANGUAGES)
    choice = st.sidebar.segmented_control(t("Language"), codes, format_func=LANGUAGES.get,
                                          default=lang(), key="lang_toggle", label_visibility="collapsed")
    choice = choice or lang()
    if choice != lang():
        set_lang(choice)
        st.rerun()


def sidebar_filters(df) -> FilterState:
    """Compact, collapsed filters. Shown only on pages where they apply."""
    active = current_filters(df).is_active()
    # Always open by default. The label must stay constant: a changing label makes Streamlit rebuild
    # the expander, which would snap it shut when filters are cleared.
    with st.sidebar.expander(t("Filters"), expanded=True):
        st.multiselect(t("Period"), T.SNAPSHOT_ORDER, key="f_snap", placeholder=t("All"))
        st.multiselect(t("Neighbourhood"), sorted(df["neighbourhood"].dropna().unique()), key="f_nbh", placeholder=t("All"))
        st.multiselect(t("Property type"), sorted(df["property_type"].dropna().unique()), key="f_type", placeholder=t("All"))
        st.multiselect(t("Rooms"), T.ROOM_BAND_ORDER, key="f_rooms", placeholder=t("Any"))
        st.slider(t("Living area (m²)"), 0.0, AREA_MAX, (0.0, AREA_MAX), step=1.0, key="f_area",
                  help=t("Capped at {max} m²; drag to the far right to include larger flats.", max=f"{AREA_MAX:.0f}"))
        st.slider(t("Year built"), 1850, 2020, (1850, 2020), key="f_year",
                  help=t("Only flats with a known year are kept when this is narrowed."))
        st.multiselect(t("Must have"), list(AMENITIES), format_func=lambda k: t(AMENITIES.get(k, k)), key="f_amen", placeholder=t("Any"))
        st.button(t("Clear filters"), on_click=reset_filters, width="stretch")
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
    if f.is_active():
        st.caption(t("Showing **{shown}** of {total} listings · {desc}",
                     shown=f"{len(out):,}", total=f"{len(df):,}", desc=f.describe()))
    return out
