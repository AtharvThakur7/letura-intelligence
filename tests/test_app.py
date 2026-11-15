"""Streamlit AppTest smoke tests: every page loads in both themes and the AI chat works in MOCK mode."""
import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import ROOT, requires_db

pytestmark = requires_db

PAGES = ["p0_home", "p1_executive", "p2_explorer", "p3_neighbourhoods", "p4_property", "p5_mietenspiegel", "p7_ai_analyst"]


def page_app(mod: str, setup: str = "") -> AppTest:
    code = f"""
import sys; sys.path.insert(0, r"{ROOT}")
import streamlit as st
from app import shared
from app.views import {mod}
shared.init_theme()
{setup}
{mod}.render()
"""
    return AppTest.from_string(code, default_timeout=120)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("mod", PAGES)
def test_every_page_loads(mod, mode):
    at = page_app(mod, f'st.session_state.theme_mode = "{mode}"').run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


def test_main_entrypoint_loads():
    at = AppTest.from_file(str(ROOT / "app" / "main.py"), default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]


def test_filters_change_listing_counts():
    all_ = page_app("p1_executive").run()
    filt = page_app("p1_executive", 'st.session_state.f_snap = ["Feb 2020"]').run()
    assert not any("Showing" in c.value for c in all_.caption)          # no filter -> no count line
    assert any("Showing **1,113** of 3,759" in c.value for c in filt.caption)


def test_empty_filter_result_is_handled():
    at = page_app("p1_executive", 'st.session_state.f_nbh = ["Horn"]; st.session_state.f_rooms = ["4.5+"]; st.session_state.f_amen = ["is_new_construction"]').run()
    assert not at.exception


def test_ai_page_mock_chat_roundtrip():
    at = page_app("p7_ai_analyst", 'st.session_state.setdefault("chat", []) if "seeded" in st.session_state else st.session_state.update(seeded=True, pending_question="Which neighbourhoods have the most rental listings?")').run()
    chat = at.session_state["chat"]
    assert chat[-1]["role"] == "assistant" and chat[-1]["results"] and chat[-1]["results"][0].ok
    assert chat[-1]["mode"] in {"mock", "live", "mock-fallback"}
