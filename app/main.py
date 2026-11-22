"""Letura Intelligence – Streamlit entry point.

Run from the project root:   streamlit run app/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app import shared  # noqa: E402
from app.views import (p0_home, p1_executive, p3_neighbourhoods, p4_property, p5_mietenspiegel,  # noqa: E402
                       p6_dashboard, p7_ai_analyst)
from letura import APP_NAME, APP_SUBTITLE  # noqa: E402
from letura.db import backend  # noqa: E402
from letura.i18n import t  # noqa: E402

st.set_page_config(page_title=f"{APP_NAME} – {APP_SUBTITLE}", page_icon="🏙️", layout="wide", initial_sidebar_state="expanded")

FILTER_URL_PATHS = {"dashboard", "market", "neighbourhoods", "properties", "ask-ai"}   # filters are only shown where they apply


def build_pages() -> list[st.Page]:
    """Rebuilt on every rerun so nav titles follow the active language."""
    return [
        st.Page(p0_home.render, title=t("Home"), icon=":material/home:", default=True, url_path="home"),
        st.Page(p6_dashboard.render, title=t("Dashboard"), icon=":material/dashboard:", url_path="dashboard"),
        st.Page(p1_executive.render, title=t("Market"), icon=":material/insights:", url_path="market"),
        st.Page(p3_neighbourhoods.render, title=t("Neighbourhoods"), icon=":material/location_city:", url_path="neighbourhoods"),
        st.Page(p4_property.render, title=t("Properties"), icon=":material/apartment:", url_path="properties"),
        st.Page(p5_mietenspiegel.render, title=t("Official rents"), icon=":material/balance:", url_path="official-rents"),
        st.Page(p7_ai_analyst.render, title=t("Letura AI"), icon=":material/smart_toy:", url_path="ask-ai"),
    ]


def main() -> None:
    shared.init_theme()
    shared.init_language()
    shared.inject_dropdown_fix()
    pages = build_pages()
    st.session_state["_pages"] = pages
    shared.sidebar_brand()
    nav = st.navigation(pages, position="hidden")
    for pg in pages:
        st.sidebar.page_link(pg)
    st.sidebar.divider()
    df = shared.load_listings_or_stop()
    if nav.url_path in FILTER_URL_PATHS:
        shared.sidebar_filters(df)
    shared.sidebar_theme_toggle()
    shared.sidebar_language_toggle()
    if backend() == "snapshot":
        st.sidebar.caption(t("Demo version · AI answers are pre-generated."))
    nav.run()
    footer = t("Letura Intelligence · Historical asking rents 2018–2020 and official 2025 reference data · "
               "Not current prices and not a legal rent determination.")
    st.markdown(f'<div class="lt-footer">{footer}</div>', unsafe_allow_html=True)


main()
