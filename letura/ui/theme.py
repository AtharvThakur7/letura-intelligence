"""Design tokens, CSS injection and Plotly styling for light & dark modes."""
from __future__ import annotations

import plotly.graph_objects as go

TOKENS = {
    "light": {
        "bg": "#f6f7f9", "surface": "#ffffff", "surface2": "#f0f2f5", "border": "#e2e5ea",
        "text": "#10131a", "text2": "#4a5160", "muted": "#7a8191", "accent": "#2a78d6", "accent_soft": "#e6f0fc",
        "grid": "#e8eaee", "good": "#0f8a5f", "warn": "#b7791f", "bad": "#c7372f",
        "shadow": "0 1px 2px rgba(16,19,26,.06)",
        "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
        "seq": ["#cde2fb", "#9ec5f4", "#5598e7", "#256abf", "#104281"],
    },
    "dark": {
        "bg": "#0e1116", "surface": "#161b22", "surface2": "#1d232c", "border": "#2a313c",
        "text": "#eef0f3", "text2": "#b6bcc8", "muted": "#8791a1", "accent": "#3987e5", "accent_soft": "#16283f",
        "grid": "#262d38", "good": "#2fbf8a", "warn": "#e0a63a", "bad": "#ef6b63",
        "shadow": "0 1px 2px rgba(0,0,0,.4)",
        "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#0ca30c", "#9085e9", "#e66767"],
        "seq": ["#16283f", "#1c5cab", "#2a78d6", "#5598e7", "#9ec5f4"],
    },
}


def tokens(mode: str) -> dict:
    return TOKENS["dark" if mode == "dark" else "light"]


def plotly_layout(mode: str) -> dict:
    t = tokens(mode)
    axis = dict(gridcolor=t["grid"], zerolinecolor=t["grid"], linecolor=t["border"], automargin=True,
                tickfont=dict(color=t["text2"]), title_font=dict(size=12, color=t["text2"]))
    return dict(
        template="plotly_white" if mode != "dark" else "plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, 'Segoe UI', system-ui, sans-serif", size=12, color=t["text2"]),
        colorway=t["series"], margin=dict(l=8, r=8, t=72, b=8),
        title=dict(font=dict(size=14, color=t["text"]), x=0, xanchor="left"),
        xaxis=axis, yaxis=axis,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=11, color=t["text2"])),
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["border"], font=dict(color=t["text"], size=12)),
        bargap=0.25,
    )


def style_fig(fig: go.Figure, mode: str, height: int = 360) -> go.Figure:
    t = tokens(mode)
    fig.update_layout(**plotly_layout(mode), height=height)
    fig.update_layout(title_font_color=t["text"])
    fig.update_traces(selector=dict(type="bar"), textfont=dict(color=t["text2"]))
    return fig


def css(mode: str) -> str:
    t = tokens(mode)
    return """
<style>
:root { --bg:%(bg)s; --surface:%(surface)s; --surface2:%(surface2)s; --border:%(border)s;
  --text:%(text)s; --text2:%(text2)s; --muted:%(muted)s; --accent:%(accent)s; --accent-soft:%(accent_soft)s;
  --good:%(good)s; --warn:%(warn)s; --bad:%(bad)s; color-scheme:%(scheme)s; }
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background:var(--bg) !important; color:var(--text);
  font-family: Inter, 'Segoe UI', system-ui, sans-serif; }
[data-testid="stHeader"] { background:transparent !important; }
.block-container { padding-top:1.4rem; padding-bottom:3rem; max-width:1400px; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div { background:var(--surface) !important; }
[data-testid="stSidebar"] { border-right:1px solid var(--border); }
h1,h2,h3,h4,h5,h6, p, label, li, [data-testid="stWidgetLabel"] p, [data-testid="stMarkdownContainer"] { color:var(--text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:var(--muted) !important; }
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="textarea"] > div, .stTextInput input,
.stNumberInput input, [data-testid="stChatInput"] textarea, [data-testid="stChatInput"] > div {
  background:var(--surface) !important; color:var(--text) !important; border-color:var(--border) !important; }
[data-baseweb="select"] span, [data-baseweb="select"] input { color:var(--text) !important; }
[data-testid="stMultiSelect"] [data-baseweb="select"] > div, [data-testid="stSelectbox"] [data-baseweb="select"] > div { background-color:var(--surface2) !important; }
svg[data-baseweb="icon"] { fill:var(--text2); }
[data-testid="stMultiSelect"] .react-aria-ComboBox > div, [data-testid="stSelectbox"] .react-aria-ComboBox > div, [data-testid="stSelectbox"] [class*="react-aria-"] > div { background-color:var(--surface2) !important; border-color:var(--border) !important; }
[data-testid="stSelectbox"] div, [data-testid="stMultiSelect"] div { color:var(--text); }
[data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input { color:var(--text) !important; -webkit-text-fill-color:var(--text); }
[role="listbox"], [role="option"], .react-aria-Popover, [data-testid="stSelectboxVirtualDropdown"], ul[role="listbox"] { background:var(--surface) !important; color:var(--text) !important; }
[role="option"]:hover { background:var(--surface2) !important; }
[data-testid="stSidebar"] svg, [data-testid="stSelectbox"] svg, [data-testid="stMultiSelect"] svg { color:var(--text2); fill:var(--text2); }
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"] { background:var(--surface) !important; color:var(--text) !important; }
[data-baseweb="tag"] { background:var(--accent-soft) !important; }
[data-baseweb="tag"] span { color:var(--accent) !important; }
.stButton > button, .stDownloadButton > button { background:var(--surface) !important; color:var(--text) !important;
  border:1px solid var(--border) !important; border-radius:8px; font-weight:500; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color:var(--accent) !important; color:var(--accent) !important; }
.stButton > button[kind="primary"] { background:var(--accent) !important; color:#fff !important; border-color:var(--accent) !important; }
[data-testid="stDataFrame"] { border:1px solid var(--border); border-radius:10px; overflow:hidden; }
[data-testid="stVerticalBlockBorderWrapper"] { background:var(--surface); border-color:var(--border) !important; border-radius:14px !important; }
[data-testid="stExpander"] { background:var(--surface); border:1px solid var(--border) !important; border-radius:10px; }
[data-testid="stExpander"] details, [data-testid="stExpander"] summary, [data-testid="stExpander"] details > div { background:var(--surface) !important; color:var(--text) !important; }
[data-testid="stExpander"] summary p { color:var(--text); font-weight:500; }
[data-testid="stChatMessage"] { background:var(--surface); border:1px solid var(--border); border-radius:12px; }
button[data-baseweb="tab"] { color:var(--text2); }
button[data-baseweb="tab"][aria-selected="true"] { color:var(--accent); }
hr { border-color:var(--border); }
[data-testid="stBottom"], [data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background-color:var(--bg) !important; }
[data-testid="stChatInput"] textarea, [data-testid="stChatInputTextArea"] { color:var(--text) !important; caret-color:var(--text); -webkit-text-fill-color:var(--text); }
[data-testid="stChatInput"] textarea::placeholder, [data-testid="stChatInputTextArea"]::placeholder { color:var(--muted) !important; -webkit-text-fill-color:var(--muted) !important; opacity:1 !important; }
[data-testid="stChatInput"] button { background:var(--surface2) !important; color:var(--text) !important; }
[data-testid="stButtonGroup"] button { background:var(--surface) !important; color:var(--text) !important; border:1px solid var(--border) !important; transition:border-color .15s, transform .15s; }
[data-testid="stButtonGroup"] button * { color:inherit !important; }
[data-testid="stButtonGroup"] button:hover { border-color:var(--accent) !important; transform:translateY(-1px); }
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[aria-pressed="true"] { background:var(--accent-soft) !important; color:var(--accent) !important; border-color:var(--accent) !important; font-weight:650; }
[data-testid="stPageLink-NavLink"], [data-testid="stPageLink-NavLink"] *, [data-testid="stPageLink"] a, [data-testid="stPageLink"] a * { color:var(--text) !important; }
[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"], [data-testid="stPageLink"] span[data-testid="stIconMaterial"] { color:var(--accent) !important; }
[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapseButton"] button *, [data-testid="stExpandSidebarButton"], [data-testid="stExpandSidebarButton"] * { color:var(--text) !important; fill:var(--text) !important; opacity:1 !important; }
[data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"] { background:var(--surface2) !important; border:1px solid var(--border) !important; border-radius:8px !important; }
[data-testid="stSidebarCollapseButton"] button:hover, [data-testid="stExpandSidebarButton"]:hover { border-color:var(--accent) !important; }
[data-testid="stSidebarCollapseButton"] button:hover *, [data-testid="stExpandSidebarButton"]:hover * { color:var(--accent) !important; fill:var(--accent) !important; }
[data-testid="stHeader"] button, [data-testid="stHeader"] button *, [data-testid="stToolbar"] button, [data-testid="stToolbar"] button * { color:var(--text2) !important; fill:var(--text2) !important; }
code, [data-testid="stMarkdownContainer"] code, .lt-pill code { background:var(--surface2) !important; color:var(--text) !important; border-radius:4px; }
[data-testid="stChatInput"] button svg { fill:var(--text2) !important; color:var(--text2) !important; }
[data-testid="stAlert"], [data-testid="stAlertContainer"] { background:var(--surface2) !important; color:var(--text) !important; border:1px solid var(--border) !important; border-radius:8px; }
[data-testid="stAlert"] *, [data-testid="stAlertContainer"] * { color:var(--text) !important; }
.lt-brand { display:flex; align-items:center; gap:.6rem; padding:.2rem 0 .8rem; }
.lt-logo { width:34px; height:34px; border-radius:9px; background:linear-gradient(135deg,var(--accent),#6250d6);
  color:#fff; display:flex; align-items:center; justify-content:center; font-weight:700; font-size:1.05rem; }
.lt-brand b { font-size:1.05rem; letter-spacing:-.01em; color:var(--text); }
.lt-brand small { display:block; color:var(--muted); font-size:.72rem; }
.lt-title { font-size:1.65rem; font-weight:700; letter-spacing:-.02em; margin:0; color:var(--text); }
.lt-desc { color:var(--text2); margin:.15rem 0 1rem; font-size:.95rem; }
.lt-kpi { background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:.9rem 1rem;
  box-shadow:%(shadow)s; height:100%%; }
.lt-kpi .l { color:var(--muted); font-size:.72rem; text-transform:uppercase; letter-spacing:.05em; font-weight:600; }
.lt-kpi .v { font-size:1.55rem; font-weight:700; color:var(--text); letter-spacing:-.02em; line-height:1.25; margin-top:.15rem; }
.lt-kpi .s { color:var(--text2); font-size:.78rem; margin-top:.1rem; }
.lt-banner { background:var(--surface); border:1px solid var(--border); border-left:4px solid var(--warn);
  border-radius:8px; padding:.65rem .9rem; color:var(--text2); font-size:.85rem; margin:.3rem 0 1rem; }
.lt-banner.info { border-left-color:var(--accent); }
.lt-section { font-size:1.02rem; font-weight:650; margin:1.3rem 0 .4rem; color:var(--text); }
.lt-pill { display:inline-block; padding:.12rem .55rem; border-radius:99px; font-size:.72rem; font-weight:600;
  background:var(--surface2); color:var(--text2); border:1px solid var(--border); margin-right:.3rem; }
.lt-pill.good { color:var(--good); } .lt-pill.warn { color:var(--warn); } .lt-pill.bad { color:var(--bad); }
.lt-pill.accent { color:var(--accent); background:var(--accent-soft); border-color:transparent; }
.lt-footer { color:var(--muted); font-size:.75rem; margin-top:2rem; border-top:1px solid var(--border); padding-top:.7rem; }
</style>
""" % {**t, "scheme": "dark" if mode == "dark" else "light"} + (DARK_EXTRA if mode == "dark" else "") + HOME_CSS


# Streamlit's data grid is canvas-rendered and ignores CSS variables; invert it in dark mode.
DARK_EXTRA = """
<style>
[data-testid="stDataFrame"] canvas { filter: invert(0.92) hue-rotate(180deg); }
[data-testid="stDataFrame"] { background:#161b22; }
</style>
"""


HOME_CSS = """
<style>
@keyframes ltFadeUp { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:none; } }
@keyframes ltGlow { 0% { transform:translate(0,0) scale(1); } 50% { transform:translate(-6%,8%) scale(1.15); } 100% { transform:translate(0,0) scale(1); } }
.lt-hero { position:relative; overflow:hidden; border-radius:20px; padding:38px 40px 32px; color:#fff;
  background:linear-gradient(135deg,#0c2455 0%,#1f5fbf 52%,#5b46d1 100%); box-shadow:0 10px 40px rgba(31,95,191,.28); margin-bottom:18px; }
.lt-hero::before { content:""; position:absolute; inset:0; background-image:linear-gradient(rgba(255,255,255,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.07) 1px,transparent 1px); background-size:34px 34px; mask-image:radial-gradient(ellipse at 70% 30%,#000 0%,transparent 70%); }
.lt-hero-glow { position:absolute; width:520px; height:520px; right:-120px; top:-200px; border-radius:50%; background:radial-gradient(circle,rgba(130,170,255,.55),transparent 65%); animation:ltGlow 11s ease-in-out infinite; }
.lt-hero > *:not(.lt-hero-glow) { position:relative; animation:ltFadeUp .7s ease both; }
.lt-hero-tag { display:inline-block; font-size:.72rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; padding:4px 12px; border-radius:99px; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.28); }
.lt-hero h1 { font-size:2.7rem; line-height:1.08; margin:14px 0 6px; letter-spacing:-.025em; color:#fff !important; font-weight:800; }
.lt-hero-sub { font-size:1.28rem; font-weight:600; margin:0 0 10px; color:#e6efff !important; max-width:760px; animation-delay:.1s; }
.lt-hero-text { font-size:.98rem; max-width:780px; color:#d3e1fb !important; line-height:1.55; animation-delay:.2s; }
.lt-hero-chips { margin-top:16px; animation-delay:.3s; }
.lt-hero-chips span { display:inline-block; margin:0 8px 6px 0; padding:5px 14px; border-radius:99px; font-size:.8rem; font-weight:650; background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.3); }
.lt-kpi { transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease; }
.lt-kpi:hover { transform:translateY(-3px); border-color:var(--accent); }
.lt-step { background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:16px 18px; animation:ltFadeUp .45s ease both; }
.lt-step h4 { margin:0 0 4px; font-size:1.05rem; color:var(--text); }
.lt-step p, .lt-step li { color:var(--text2); font-size:.92rem; }
.lt-answer { background:var(--surface); border:1px solid var(--border); border-left:4px solid var(--accent); border-radius:12px; padding:14px 18px; animation:ltFadeUp .4s ease both; }
@media (max-width: 640px) { .lt-hero { padding:24px 20px; } .lt-hero h1 { font-size:2rem; } }
</style>
"""
