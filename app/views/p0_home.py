"""Home – landing page: what Letura Intelligence is, live numbers, and interactive entry points."""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from app import shared
from letura.ai.analyst import Analyst
from letura.analytics import repo, stats, transforms as T
from letura.ui import ai_render, components as C, theme

SHOWCASE_QUESTIONS = [
    "Which neighbourhoods have the highest median advertised rents?",
    "How did median advertised rent change across the available snapshots?",
    "Do larger apartments have lower advertised rent per square metre?",
    "How does rent differ between apartments with and without balconies?",
    "Show the Mietenspiegel range for a Gute Wohnlage built 1994 to 2010.",
    "Which columns have the most missing values?",
]
PAGE_BLURBS = {
    "Executive Overview": "Headline KPIs, trend and distributions",
    "Rental Market Explorer": "Filter, search and export listings",
    "Neighbourhood Analysis": "Rank and compare Hamburg areas",
    "Property Insights": "Size, age, type and amenities",
    "Mietenspiegel Benchmark": "Official 2025 reference rents",
    "Data Quality & Pipeline": "Checks, gaps and reconciliation",
    "AI Rental Analyst": "Ask questions in plain English",
}


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


def render() -> None:
    df = shared.load_listings_or_stop()
    t = theme.tokens(C.mode())
    try:
        dq = repo.load_table("analytics_data_quality")
        checks_total = len(dq)
        checks_failed = int((dq.status == "fail").sum())
    except Exception:  # noqa: BLE001
        checks_total, checks_failed = 0, 0

    # ---- hero
    st.markdown("""
<div class="lt-hero"><div class="lt-hero-glow"></div>
  <span class="lt-hero-tag">PropTech · Hamburg · Data + AI</span>
  <h1>Letura Intelligence</h1>
  <p class="lt-hero-sub">From raw rental data to clear decisions: one platform for Hamburg's rental market.</p>
  <p class="lt-hero-text">Public rental listings, official reference rents and street-level location data flow through a governed
  MySQL pipeline into an interactive dashboard, and an AI analyst that answers in plain English from real query results.
  Explore it below: every number is traceable, and every limitation is shown.</p>
  <div class="lt-hero-chips"><span>MySQL</span><span>Python</span><span>Streamlit + Plotly</span><span>OpenAI</span><span>Light &amp; dark mode</span></div>
</div>""", unsafe_allow_html=True)

    counters([
        ("Hamburg listings", float(len(df)), 0, "", ""),
        ("Neighbourhoods", float(df["neighbourhood"].nunique()), 0, "", ""),
        ("Median asking rent", float(df["rent_per_sqm"].median()), 2, "€", "/m²"),
        ("Snapshots 2018–2020", float(df["snapshot"].astype(str).nunique()), 0, "", ""),
        (f"Quality checks · {checks_failed} failed", float(checks_total), 0, "", ""),
    ])

    # ---- ask the market (interactive)
    C.section("Ask the market", "Pick a question: the AI analyst's answer, chart and calculation details appear instantly. Answers were generated by the live AI from the database.")
    choice = st.pills("Ask the market", SHOWCASE_QUESTIONS, default=SHOWCASE_QUESTIONS[0], key="home_q", label_visibility="collapsed")
    if choice:
        reply = Analyst.stored_answer(choice)
        if reply is None:
            with st.spinner("Asking the analyst…"):
                reply = Analyst().answer(choice, [], None, False)
        with st.container(border=True):
            st.markdown(reply.text)
            for i, r in enumerate(reply.results[:1]):
                ai_render.render_result(r, f"home_{abs(hash(choice)) % 10**6}_{i}")
            st.caption(reply.notice or f"{reply.mode} answer")
        st.page_link(st.session_state["_pages"][-1], label="Open the full AI Rental Analyst", icon=":material/smart_toy:") if "_pages" in st.session_state else None

    # ---- treemap
    C.section("Hamburg rental market at a glance", "Box size = number of listings · colour = median advertised rent (€/m²). Click a district to zoom in; click the bar at the top to zoom out.")
    snap = st.segmented_control("Snapshot", ["All snapshots"] + T.SNAPSHOT_ORDER, default="All snapshots", key="home_snap") or "All snapshots"
    C.show(treemap(df, snap), 520, "home_tree")
    st.caption("Historical advertised rents (2018–2020). Small boxes have few listings; medians there are indicative only.")

    # ---- journey
    C.section("The data journey", "How raw public data becomes a trustworthy answer.")
    step = st.segmented_control("Step", ["1 · Collect", "2 · Store & clean", "3 · Analyse", "4 · Ask the AI"], default="1 · Collect", key="home_step", label_visibility="collapsed") or "1 · Collect"
    out_high = int((df.outlier_iqr_global != "normal").sum())
    steps = {
        "1 · Collect": ("Three public datasets", ["<b>268,850</b> ImmoScout24 listings (Kaggle) → <b>3,759</b> in Hamburg, 2018–2020",
                                                  "<b>88</b> official Mietenspiegel 2025 reference rents (hamburg.de)",
                                                  "<b>26,205</b> street ranges from the Wohnlagenverzeichnis 2025"]),
        "2 · Store & clean": ("Raw → cleaned → enriched in MySQL", ["Raw tables are loaded as delivered and <b>never edited</b>",
                                                                     "Types fixed, rent per m² calculated, neighbourhood and size bands added",
                                                                     f"<b>{out_high}</b> high-rent outliers flagged and <b>kept</b>; missing values stay missing"]),
        "3 · Analyse": ("Median, percentiles and sample sizes", ["Per snapshot, neighbourhood, property type and amenity",
                                                                  f"<b>{checks_total}</b> automated quality checks, <b>{checks_failed}</b> failed",
                                                                  "Official 2025 reference rents shown beside 2018–2020 asking rents, for context only"]),
        "4 · Ask the AI": ("An analyst that cannot make things up", ["Chooses from 8 approved database tools, read-only access",
                                                                     "Every figure comes from a query result, shown with sample size and filters",
                                                                     "Never presents 2018–2020 rents as today's prices"]),
    }
    title, bullets = steps[step]
    st.markdown(f'<div class="lt-step"><h4>{title}</h4><ul>' + "".join(f"<li>{b}</li>" for b in bullets) + "</ul></div>", unsafe_allow_html=True)

    # ---- explore
    C.section("Explore the platform")
    pages = st.session_state.get("_pages", [])
    cols = st.columns(3)
    for i, pg in enumerate(pages[1:]):
        with cols[i % 3]:
            st.page_link(pg, label=pg.title, icon=pg.icon)
            st.caption(PAGE_BLURBS.get(pg.title, ""))

    C.banner("Showcase edition: built on historical asking rents (2018–2020) and official 2025 reference data. Not current market prices and not a legal rent determination.", "info")
