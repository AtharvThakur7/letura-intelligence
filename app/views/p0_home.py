"""Home – landing page: what Letura Intelligence is, live numbers, and interactive entry points."""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from app import shared
from letura.ai.analyst import Analyst
from letura.analytics import transforms as T
from letura.ui import ai_render, components as C, theme

SHOWCASE_QUESTIONS = [
    "Which neighbourhoods have the highest median advertised rents?",
    "How did median advertised rent change across the available snapshots?",
    "Do larger apartments have lower advertised rent per square metre?",
    "How does rent differ between apartments with and without balconies?",
    "Show the Mietenspiegel range for a Gute Wohnlage built 1994 to 2010.",
    "Which columns have the most missing values?",
]


def counters(items: list[tuple[str, float, int, str, str]]) -> None:
    """Animated count-up KPI strip. items = (label, value, decimals, prefix, suffix)."""
    t = theme.tokens(C.mode())
    cards = "".join(
        f'<div class="c"><div class="v" data-t="{v}" data-d="{d}" data-p="{html.escape(p)}" data-s="{html.escape(s)}">0</div>'
        f'<div class="l">{html.escape(label)}</div></div>' for label, v, d, p, s in items)
    components.html(f"""
<style>
 html,body{{margin:0;background:transparent;font-family:'Segoe UI',Inter,Arial,sans-serif}}
 .row{{display:grid;grid-template-columns:repeat({len(items)},1fr);gap:10px}}
 .c{{background:{t['surface']};border:1px solid {t['border']};border-radius:14px;padding:14px 14px 12px;transition:transform .18s,border-color .18s}}
 .c:hover{{transform:translateY(-3px);border-color:{t['accent']}}}
 .v{{font-size:30px;font-weight:800;letter-spacing:-.02em;color:{t['text']};line-height:1.15}}
 .l{{font-size:10.5px;letter-spacing:.07em;text-transform:uppercase;color:{t['muted']};margin-top:3px;font-weight:600}}
 @media(max-width:720px){{.row{{grid-template-columns:repeat(2,1fr)}}.v{{font-size:24px}}}}
</style>
<div class="row">{cards}</div>
<script>
 const ease=x=>1-Math.pow(1-x,3);
 document.querySelectorAll('.v').forEach(el=>{{
   const T=parseFloat(el.dataset.t),D=parseInt(el.dataset.d),P=el.dataset.p,S=el.dataset.s,t0=performance.now(),dur=1300;
   const fmt=v=>P+v.toLocaleString('en-US',{{minimumFractionDigits:D,maximumFractionDigits:D}})+S;
   (function f(now){{const k=Math.min((now-t0)/dur,1);el.textContent=fmt(T*ease(k));if(k<1)requestAnimationFrame(f);else el.textContent=fmt(T);}})(t0);
 }});
</script>""", height=118 if len(items) <= 5 else 130)


def treemap(df: pd.DataFrame, snapshot: str) -> go.Figure:
    t = theme.tokens(C.mode())
    d = df if snapshot == "All snapshots" else df[df["snapshot"].astype(str) == snapshot]
    d = d.dropna(subset=["neighbourhood", "bezirk", "rent_per_sqm"])
    nb = d.groupby(["bezirk", "neighbourhood"]).agg(n=("rent_per_sqm", "size"), med=("rent_per_sqm", "median")).reset_index()
    bz = d.groupby("bezirk").agg(n=("rent_per_sqm", "size"), med=("rent_per_sqm", "median")).reset_index()
    ids = ["Hamburg"] + [f"B|{b}" for b in bz.bezirk] + [f"N|{b}|{n}" for b, n in zip(nb.bezirk, nb.neighbourhood)]
    labels = ["Hamburg"] + list(bz.bezirk) + list(nb.neighbourhood)
    parents = [""] + ["Hamburg"] * len(bz) + [f"B|{b}" for b in nb.bezirk]
    values = [int(len(d))] + list(bz.n.astype(int)) + list(nb.n.astype(int))
    meds = [float(d.rent_per_sqm.median())] + list(bz.med.astype(float)) + list(nb.med.astype(float))
    lo, hi = float(nb.med.quantile(.05)), float(nb.med.quantile(.95))
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=meds, colorscale=[[i / 4, c] for i, c in enumerate(t["seq"])], cmin=lo, cmax=hi, line=dict(width=1.5, color=t["surface"]),
                    colorbar=dict(title="€/m²", thickness=12, len=.8)),
        customdata=list(zip(values, meds)), textinfo="label",
        hovertemplate="<b>%{label}</b><br>Median €%{customdata[1]:.2f}/m²<br>%{customdata[0]} listings<extra></extra>",
        pathbar=dict(visible=True), tiling=dict(pad=3)))
    fig.update_layout(margin=dict(l=0, r=0, t=6, b=0))
    return fig


def _page(title: str):
    return next((p for p in st.session_state.get("_pages", []) if p.title == title), None)


def render() -> None:
    df = shared.load_listings_or_stop()

    # ---- hero (kept light: one idea, two sentences)
    st.markdown("""
<div class="lt-hero"><div class="lt-hero-glow"></div>
  <h1>Letura Intelligence</h1>
  <p class="lt-hero-sub">Hamburg's rental market, made simple.</p>
  <p class="lt-hero-text">See what flats cost in every neighbourhood, compare with official reference rents,
  and ask questions in plain English.</p>
</div>""", unsafe_allow_html=True)

    counters([
        ("Hamburg listings", float(len(df)), 0, "", ""),
        ("Neighbourhoods", float(df["neighbourhood"].nunique()), 0, "", ""),
        ("Median asking rent", float(df["rent_per_sqm"].median()), 2, "€", "/m²"),
        ("Periods covered 2018–2020", float(df["snapshot"].astype(str).nunique()), 0, "", ""),
    ])

    # ---- three clear next steps
    cols = st.columns(3)
    for col, (title, label, icon) in zip(cols, [("Market", "See the market overview", ":material/insights:"),
                                                ("Neighbourhoods", "Compare neighbourhoods", ":material/location_city:"),
                                                ("Ask AI", "Ask the AI analyst", ":material/smart_toy:")]):
        pg = _page(title)
        if pg is not None:
            with col:
                st.page_link(pg, label=label, icon=icon, width="stretch")

    # ---- ask the market (interactive)
    C.section("Try a question")
    choice = st.pills("Question", SHOWCASE_QUESTIONS, default=SHOWCASE_QUESTIONS[0], key="home_q", label_visibility="collapsed")
    if choice:
        reply = Analyst.stored_answer(choice)
        if reply is None:
            with st.spinner("Thinking…"):
                reply = Analyst().answer(choice, [], None, False)
        with st.container(border=True):
            st.markdown(reply.text)
            for i, r in enumerate(reply.results[:1]):
                ai_render.render_result(r, f"home_{abs(hash(choice)) % 10**6}_{i}")

    # ---- treemap
    C.section("Hamburg at a glance", "Bigger box = more listings · darker = higher rent. Click a district to zoom in.")
    snap = st.segmented_control("Period", ["All"] + T.SNAPSHOT_ORDER, default="All", key="home_snap", label_visibility="collapsed") or "All"
    C.show(treemap(df, "All snapshots" if snap == "All" else snap), 480, "home_tree")

    st.caption("Based on historical asking rents (2018–2020) and official 2025 reference rents. Not current prices and not a legal rent determination.")
