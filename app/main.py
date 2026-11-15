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
from app.views import (p0_home, p1_executive, p3_neighbourhoods, p4_property, p5_mietenspiegel, p6_quality,  # noqa: E402
                       p7_ai_analyst)
from letura import APP_NAME, APP_SUBTITLE  # noqa: E402
from letura.db import backend  # noqa: E402

st.set_page_config(page_title=f"{APP_NAME} – {APP_SUBTITLE}", page_icon="🏙️", layout="wide", initial_sidebar_state="expanded")

PAGES = [
    st.Page(p0_home.render, title="Home", icon=":material/home:", default=True),
    st.Page(p1_executive.render, title="Market", icon=":material/insights:", url_path="market"),
    st.Page(p3_neighbourhoods.render, title="Neighbourhoods", icon=":material/location_city:", url_path="neighbourhoods"),
    st.Page(p4_property.render, title="Properties", icon=":material/apartment:", url_path="properties"),
    st.Page(p5_mietenspiegel.render, title="Official rents", icon=":material/balance:", url_path="official-rents"),
    st.Page(p7_ai_analyst.render, title="Ask AI", icon=":material/smart_toy:", url_path="ask-ai"),
    st.Page(p6_quality.render, title="Data & sources", icon=":material/fact_check:", url_path="data"),
]
FILTER_PAGES = {"Market", "Neighbourhoods", "Properties", "Ask AI"}   # filters are only shown where they apply


def main() -> None:
    shared.init_theme()
    st.session_state["_pages"] = PAGES
    shared.sidebar_brand()
    nav = st.navigation(PAGES, position="hidden")
    for pg in PAGES:
        st.sidebar.page_link(pg)
    st.sidebar.divider()
    df = shared.load_listings_or_stop()
    if nav.title in FILTER_PAGES:
        shared.sidebar_filters(df)
    shared.sidebar_theme_toggle()
    if backend() == "snapshot":
        st.sidebar.caption("Demo version · AI answers are pre-generated.")
    nav.run()
    st.markdown('<div class="lt-footer">Letura Intelligence · Historical asking rents 2018–2020 and official 2025 reference data · '
                'Not current prices and not a legal rent determination.</div>', unsafe_allow_html=True)


main()
