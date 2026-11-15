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
from app.views import p0_home, p1_executive, p2_explorer, p3_neighbourhoods, p4_property, p5_mietenspiegel, p6_quality, p7_ai_analyst  # noqa: E402
from letura import APP_NAME, APP_SUBTITLE  # noqa: E402
from letura.db import backend  # noqa: E402

st.set_page_config(page_title=f"{APP_NAME} – {APP_SUBTITLE}", page_icon="🏙️", layout="wide", initial_sidebar_state="expanded")

PAGES = [
    st.Page(p0_home.render, title="Home", icon=":material/home:", default=True),
    st.Page(p1_executive.render, title="Executive Overview", icon=":material/dashboard:", url_path="overview"),
    st.Page(p2_explorer.render, title="Rental Market Explorer", icon=":material/search:", url_path="explorer"),
    st.Page(p3_neighbourhoods.render, title="Neighbourhood Analysis", icon=":material/location_city:", url_path="neighbourhoods"),
    st.Page(p4_property.render, title="Property Insights", icon=":material/apartment:", url_path="property"),
    st.Page(p5_mietenspiegel.render, title="Mietenspiegel Benchmark", icon=":material/balance:", url_path="mietenspiegel"),
    st.Page(p6_quality.render, title="Data Quality & Pipeline", icon=":material/verified:", url_path="quality"),
    st.Page(p7_ai_analyst.render, title="AI Rental Analyst", icon=":material/smart_toy:", url_path="analyst"),
]


def main() -> None:
    shared.init_theme()
    st.session_state["_pages"] = PAGES
    shared.sidebar_brand()
    if backend() == "snapshot":
        st.sidebar.markdown('<div class="lt-banner info">Showcase edition: bundled data snapshot, AI in demo mode.</div>', unsafe_allow_html=True)
    nav = st.navigation(PAGES, position="hidden")
    for pg in PAGES:
        st.sidebar.page_link(pg)
    st.sidebar.divider()
    df = shared.load_listings_or_stop()
    shared.sidebar_filters(df)
    shared.sidebar_theme_toggle()
    nav.run()
    st.markdown('<div class="lt-footer">Letura Intelligence · Historical advertised rents 2018–2020 and official Mietenspiegel 2025 · '
                'Not current market prices and not a legal rent determination.</div>', unsafe_allow_html=True)


main()
