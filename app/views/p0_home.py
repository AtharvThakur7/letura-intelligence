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
from letura.i18n import t
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


def _page(url_path: str):
    return next((p for p in st.session_state.get("_pages", []) if p.url_path == url_path), None)


def _skyline_svg() -> str:
    """Flat-design Hamburg skyline silhouette for the hero — ties the page to the real-estate business."""
    buildings = [(0, 96, 46, 0.10), (44, 58, 54, 0.14), (96, 118, 38, 0.10),
                 (132, 28, 60, 0.18), (190, 70, 40, 0.12), (228, 32, 52, 0.15)]
    rects = []
    for x, y, h, op in buildings:
        rects.append(f'<rect x="{x}" y="{160 - h}" width="{y}" height="{h}" rx="2" fill="rgba(255,255,255,{op})"/>')
        rows = max(2, h // 22)
        cols = max(2, y // 16)
        for r in range(rows):
            for c in range(cols):
                wx, wy = x + 6 + c * 14, 160 - h + 8 + r * 20
                if wy < 150 and wx < x + y - 8:
                    rects.append(f'<rect x="{wx}" y="{wy}" width="6" height="9" rx="1" fill="rgba(255,214,122,.55)"/>')
    return (f'<svg class="lt-hero-skyline" viewBox="0 0 260 160" preserveAspectRatio="xMaxYMax meet" '
            f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{"".join(rects)}</svg>')


FEATURES = [
    ("dashboard", "📊", ":material/dashboard:", "Dashboard",
     "One executive view of the whole market: headline KPIs, trend sparklines and auto-generated insights."),
    ("market", "📈", ":material/insights:", "Market",
     "The city-wide picture: price trends, distribution and property mix at a glance."),
    ("neighbourhoods", "🏙️", ":material/location_city:", "Neighbourhoods",
     "Rank, compare and benchmark every Hamburg neighbourhood and district."),
    ("properties", "🏢", ":material/apartment:", "Properties",
     "See how size, age, type and features move the price per m²."),
    ("official-rents", "⚖️", ":material/balance:", "Official rents",
     "Benchmark advertised rents against Hamburg's official 2025 Mietenspiegel."),
    ("ask-ai", "🤖", ":material/smart_toy:", "Letura AI",
     "Get a straight answer in plain language, backed by the real numbers behind it."),
]


def render() -> None:
    df = shared.load_listings_or_stop()

    # ---- hero: a product pitch, not a data dump — the live numbers have their own section below
    tag = t("Hamburg rental market intelligence")
    hero_sub = t("The rental market intelligence platform for Hamburg real estate.")
    hero_text = t("Letura Intelligence turns raw listing data into pricing benchmarks, neighbourhood comparisons "
                  "and official-rent compliance checks — so landlords, investors and analysts can price with "
                  "confidence and back every decision with evidence.")
    st.markdown(f"""
<div class="lt-hero"><div class="lt-hero-glow"></div>{_skyline_svg()}
  <span class="lt-hero-tag">{html.escape(tag)}</span>
  <h1>Letura Intelligence</h1>
  <p class="lt-hero-sub">{hero_sub}</p>
  <p class="lt-hero-text">{hero_text}</p>
</div>""", unsafe_allow_html=True)

    counters([
        (t("Hamburg listings"), float(len(df)), 0, "", ""),
        (t("Neighbourhoods"), float(df["neighbourhood"].nunique()), 0, "", ""),
        (t("Median asking rent"), float(df["rent_per_sqm"].median()), 2, "€", "/m²"),
        (t("Periods covered 2018–2020"), float(df["snapshot"].astype(str).nunique()), 0, "", ""),
    ])

    # ---- what we built: a feature tour that doubles as navigation
    C.section(t("What Letura Intelligence gives you"),
              t("Six tools, one dataset — each one answers a different question a landlord, investor or analyst would ask."))
    for row in (FEATURES[:3], FEATURES[3:]):
        cols = st.columns(3)
        for col, (url_path, emoji, icon, title, desc) in zip(cols, row):
            pg = _page(url_path)
            with col:
                with st.container(border=True):
                    st.markdown(f'<div class="lt-feat-icon">{emoji}</div>', unsafe_allow_html=True)
                    st.markdown(f"**{t(title)}**")
                    st.caption(t(desc))
                    if pg is not None:
                        st.page_link(pg, label=t("Open"), icon=icon, width="stretch")

    # ---- ask the market (interactive)
    C.section(t("Try a question"))
    choice = st.pills(t("Question"), SHOWCASE_QUESTIONS, default=SHOWCASE_QUESTIONS[0], key="home_q", label_visibility="collapsed")
    if choice:
        reply = Analyst.stored_answer(choice)
        if reply is None:
            with st.spinner(t("Thinking…")):
                reply = Analyst().answer(choice, [], None, False)
        with st.container(border=True):
            st.markdown(reply.text)
            for i, r in enumerate(reply.results[:1]):
                ai_render.render_result(r, f"home_{abs(hash(choice)) % 10**6}_{i}")

    # ---- treemap
    C.section(t("Hamburg at a glance"), t("Bigger box = more listings · darker = higher rent. Click a district to zoom in."))
    snap = st.segmented_control(t("Period"), ["All"] + T.SNAPSHOT_ORDER, default="All", key="home_snap",
                                format_func=lambda v: t("All") if v == "All" else v, label_visibility="collapsed") or "All"
    C.show(treemap(df, "All snapshots" if snap == "All" else snap), 480, "home_tree")

    st.caption(t("Based on historical asking rents (2018–2020) and official 2025 reference rents. "
                 "Not current prices and not a legal rent determination."))
