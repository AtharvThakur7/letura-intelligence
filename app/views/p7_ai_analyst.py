"""Ask AI: a simple chat that answers from the Hamburg rental data."""
from __future__ import annotations

import streamlit as st

from app import shared
from letura.ai.analyst import SUGGESTED_QUESTIONS, Analyst
from letura.ui import ai_render, components as C

FEATURED = [
    "What is the median advertised rent per square metre in Hamburg?",
    "Which neighbourhoods have the highest median advertised rents?",
    "How did median advertised rent change across the available snapshots?",
    "Do larger apartments have lower advertised rent per square metre?",
    "How does rent differ between apartments with and without balconies?",
    "Prepare an executive summary of the available market data.",
]


def get_analyst() -> Analyst:
    """Cheap to build; deliberately not cached so a code update is never masked by a stale instance."""
    return Analyst()


def _ask(question: str) -> None:
    st.session_state["pending_question"] = question


def render() -> None:
    C.page_header("Ask AI", "Ask about Hamburg rents in plain English. Every answer shows the numbers it is based on.")
    df_all = shared.load_listings_or_stop()
    analyst = get_analyst()
    filters = shared.current_filters(df_all)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("ai_tokens", 0)

    if analyst.showcase_note():
        st.caption("Demo version: the suggested questions show answers prepared in advance by the AI analyst. Questions you type use the built-in analysis.")

    use_filters = True
    if filters.is_active():
        use_filters = st.toggle(f"Use my filters ({filters.describe()})", value=True, key="ai_use_filters")

    if not st.session_state["chat"]:
        st.markdown("**Try one of these**")
        cols = st.columns(2)
        for i, q in enumerate(FEATURED):
            with cols[i % 2]:
                st.button(q, key=f"sq_f{i}", on_click=_ask, args=(q,), width="stretch")
    with st.expander("More questions"):
        for cat, qs in SUGGESTED_QUESTIONS.items():
            st.caption(cat)
            for i, q in enumerate(qs):
                if q not in FEATURED:
                    st.button(q, key=f"sq_{cat}_{i}", on_click=_ask, args=(q,), width="stretch")

    for i, m in enumerate(st.session_state["chat"]):
        with st.chat_message(m["role"]):
            if m["role"] == "user":
                st.markdown(m["content"])
            else:
                if m.get("notice") and m.get("mode") != "showcase":
                    st.warning(m["notice"])
                st.markdown(m["content"])
                for j, r in enumerate(m.get("results", [])):
                    ai_render.render_result(r, f"chat{i}_{j}")

    typed = st.chat_input("Ask about rents, neighbourhoods, property types or the official 2025 rents…")
    question = st.session_state.pop("pending_question", None) or typed
    if question:
        st.session_state["chat"].append({"role": "user", "content": question})
        history = [{"role": m["role"], "content": m["content"], "tool_calls": m.get("tool_calls"), "memory": m.get("memory")}
                   for m in st.session_state["chat"][:-1]]
        with st.spinner("Looking at the data…"):
            reply = analyst.answer(question, history, filters, use_filters)
        st.session_state["ai_tokens"] += reply.tokens
        st.session_state["chat"].append({"role": "assistant", "content": reply.text, "results": reply.results, "mode": reply.mode,
                                         "notice": reply.notice, "tool_calls": reply.tool_calls, "seconds": reply.seconds, "tokens": reply.tokens})
        st.rerun()

    if st.session_state["chat"] and st.button("Start over"):
        st.session_state["chat"] = []
        st.rerun()
