"""Page 7 – AI Rental Market Analyst."""
from __future__ import annotations

import streamlit as st

from app import shared
from letura.ai.analyst import SUGGESTED_QUESTIONS, Analyst
from letura.ui import ai_render, components as C


def get_analyst() -> Analyst:
    """Cheap to build (settings are cached, the OpenAI client is created lazily).

    Deliberately NOT cached with st.cache_resource: a cached instance survives code updates
    on Streamlit Cloud and would keep serving an outdated class.
    """
    return Analyst()


def _ask(question: str) -> None:
    st.session_state["pending_question"] = question


def render() -> None:
    C.page_header("AI Rental Market Analyst", "Ask questions in plain English. Every number comes from MySQL through approved analytics tools.")
    df_all = shared.load_listings_or_stop()
    analyst = get_analyst()
    filters = shared.current_filters(df_all)
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("ai_tokens", 0)

    top = st.columns([3, 2, 1])
    with top[0]:
        live = analyst.mode == "live"
        C.pills([(("● " if live else "○ ") + analyst.status_text(), "good" if live else "warn")])
    with top[1]:
        scope = st.radio("Question scope", ["Use active dashboard filters", "Independent (ignore filters)"], horizontal=False,
                         key="ai_scope", label_visibility="collapsed")
    with top[2]:
        st.button("Reset filters", on_click=shared.reset_filters, width="stretch", key="ai_reset")
    note = analyst.showcase_note()
    if note:
        st.caption(note + " Click a suggested question below; custom questions use the built-in demo analysis.")
    use_filters = scope.startswith("Use")
    if use_filters and filters.is_active():
        C.banner("Active dashboard filters will be applied to every answer: " + filters.describe(), "info")
    elif not use_filters:
        C.banner("Independent mode: dashboard filters are ignored for this conversation.", "info")
    else:
        st.caption("No dashboard filters active – answers cover all 3,759 Hamburg listings.")

    with st.expander("Suggested questions", expanded=not st.session_state["chat"]):
        tabs = st.tabs(list(SUGGESTED_QUESTIONS))
        for tab, (cat, qs) in zip(tabs, SUGGESTED_QUESTIONS.items()):
            with tab:
                for i, q in enumerate(qs):
                    st.button(q, key=f"sq_{cat}_{i}", on_click=_ask, args=(q,), width="stretch")

    for i, m in enumerate(st.session_state["chat"]):
        with st.chat_message(m["role"]):
            if m["role"] == "user":
                st.markdown(m["content"])
                if m.get("scope"):
                    st.caption(m["scope"])
            else:
                if m.get("notice"):
                    st.warning(m["notice"])
                st.markdown(m["content"])
                for j, r in enumerate(m.get("results", [])):
                    ai_render.render_result(r, f"chat{i}_{j}")
                st.caption(f"{m.get('mode', '')} · {m.get('seconds', 0)}s" + (f" · {m['tokens']} tokens" if m.get("tokens") else ""))

    typed = st.chat_input("Ask about Hamburg rents, neighbourhoods, property types, the Mietenspiegel or data quality…")
    question = st.session_state.pop("pending_question", None) or typed
    if question:
        scope_txt = f"Scope: {filters.describe()}" if use_filters and filters.is_active() else ("Scope: independent" if not use_filters else "Scope: all listings")
        st.session_state["chat"].append({"role": "user", "content": question, "scope": scope_txt})
        history = [{"role": m["role"], "content": m["content"], "tool_calls": m.get("tool_calls"), "memory": m.get("memory")}
                   for m in st.session_state["chat"][:-1]]
        with st.spinner("Querying the database and analysing…"):
            reply = analyst.answer(question, history, filters, use_filters)
        st.session_state["ai_tokens"] += reply.tokens
        st.session_state["chat"].append({"role": "assistant", "content": reply.text, "results": reply.results, "mode": reply.mode,
                                         "notice": reply.notice, "tool_calls": reply.tool_calls, "seconds": reply.seconds, "tokens": reply.tokens})
        st.rerun()

    with st.sidebar:
        if st.session_state["chat"]:
            if st.button("Clear conversation", width="stretch"):
                st.session_state["chat"] = []
                st.rerun()
        if st.session_state["ai_tokens"]:
            st.caption(f"Tokens used this session: {st.session_state['ai_tokens']:,}")
