"""Visual theme: soft gradient background, navy-to-teal sidebar, card-style panels.

Pure styling - no effect on evaluation logic. Call apply_theme() once, right after
st.set_page_config(), and header() in place of st.title().
"""
from __future__ import annotations

import html

import streamlit as st

NAVY = "#0B2545"
NAVY_2 = "#13315C"
TEAL = "#0F766E"
TEAL_LIGHT = "#14B8A6"
INK = "#0F172A"
MUTED = "#475569"
BORDER = "#E2E8F0"

_CSS = f"""
<style>
/* ---------- page background ---------- */
[data-testid="stAppViewContainer"] {{
    background: linear-gradient(160deg, #F4F7FB 0%, #EAF2F7 45%, #E6F4F1 100%);
    background-attachment: fixed;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; max-width: 1280px; }}

/* ---------- sidebar: navy to teal ---------- */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {NAVY} 0%, {NAVY_2} 45%, {TEAL} 100%);
    border-right: none;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] small, [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
    color: #E8F1F8 !important;
}}
[data-testid="stSidebar"] strong {{ color: #FFFFFF !important; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: #CFE3EE !important; opacity: 1; }}
[data-testid="stSidebar"] [data-testid="stTooltipIcon"] * {{ color: #CFE3EE !important; stroke: #CFE3EE; opacity: 1; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.18); }}
/* keep text inside inputs / dropdowns dark on their white background */
[data-testid="stSidebar"] [data-baseweb="select"] *, [data-testid="stSidebar"] input {{
    color: {INK} !important;
}}
[data-testid="stSidebar"] [data-baseweb="select"] > div, [data-testid="stSidebar"] input {{
    border-radius: 10px;
}}
[data-testid="stSidebar"] .stButton button {{
    background: rgba(255,255,255,0.12); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.35);
}}
[data-testid="stSidebar"] .stButton button:hover {{
    background: rgba(255,255,255,0.22); border-color: #FFFFFF; color: #FFFFFF;
}}
[data-testid="stSidebar"] .stButton button p {{ color: #FFFFFF !important; }}

/* ---------- hero header ---------- */
.rfp-hero {{
    background: linear-gradient(120deg, {NAVY} 0%, {NAVY_2} 50%, {TEAL} 100%);
    border-radius: 18px; padding: 26px 32px; margin-bottom: 18px;
    box-shadow: 0 10px 30px rgba(11, 37, 69, 0.18);
}}
.rfp-hero h1 {{ color: #FFFFFF; font-size: 2.0rem; font-weight: 700; margin: 0 0 6px 0; padding: 0; }}
.rfp-hero p {{ color: #D6E6F2; margin: 0; font-size: 0.98rem; }}
.rfp-pills {{ margin-top: 14px; display: flex; gap: 8px; flex-wrap: wrap; }}
.rfp-pill {{
    background: rgba(255,255,255,0.14); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.28);
    padding: 4px 12px; border-radius: 999px; font-size: 0.8rem;
}}

/* ---------- tabs as pills (selectors for both older and newer Streamlit versions) ---------- */
.stTabs [data-baseweb="tab-list"], [role="tablist"] {{
    gap: 6px; background: #FFFFFF; padding: 6px; border-radius: 14px;
    border: 1px solid {BORDER}; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}}
.stTabs [data-baseweb="tab"], [role="tab"] {{
    height: 40px; padding: 0 16px; border-radius: 10px; background: transparent;
    display: flex; align-items: center; cursor: pointer;
}}
[role="tab"]:hover {{ background: #F1F5F9; }}
[role="tab"] p {{ font-weight: 500; color: {MUTED}; margin: 0; }}
.stTabs [aria-selected="true"], [role="tab"][aria-selected="true"] {{
    background: linear-gradient(120deg, {NAVY_2}, {TEAL}) !important;
}}
.stTabs [aria-selected="true"] p, [role="tab"][aria-selected="true"] p {{ color: #FFFFFF !important; }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"],
.react-aria-SelectionIndicator {{ display: none !important; }}
[role="tablist"] + div, .stTabs [data-baseweb="tab-border"] + div {{ border: none !important; }}
.stTabs [data-baseweb="tab-panel"], [role="tabpanel"] {{ padding-top: 18px; }}

/* ---------- cards ---------- */
[data-testid="stMetric"] {{
    background: #FFFFFF; border: 1px solid {BORDER}; border-top: 4px solid {TEAL};
    border-radius: 14px; padding: 14px 18px; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
}}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-weight: 500; }}
[data-testid="stMetricValue"] {{ color: {NAVY}; font-weight: 700; }}
/* let long values (run IDs, provider names) wrap instead of being cut off with "..." */
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
    overflow-wrap: anywhere; line-height: 1.15;
}}
[data-testid="stDataFrame"], [data-testid="stTable"] {{
    background: #FFFFFF; border-radius: 12px; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
}}
[data-testid="stExpander"] {{
    background: #FFFFFF; border-radius: 12px; border: 1px solid {BORDER};
}}
[data-testid="stFileUploaderDropzone"] {{ background: #FFFFFF; border-radius: 12px; }}
[data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {{
    background: #FFFFFF; border-radius: 14px; border: 1px solid {BORDER}; overflow: hidden;
}}

/* ---------- headings & buttons ---------- */
h2, h3, h4 {{ color: {NAVY}; }}
.stButton button[kind="primary"], .stDownloadButton button[kind="primary"] {{
    background: linear-gradient(120deg, {NAVY_2}, {TEAL}); border: none; color: #FFFFFF;
    box-shadow: 0 4px 12px rgba(15, 118, 110, 0.25);
}}
.stButton button[kind="primary"]:hover, .stDownloadButton button[kind="primary"]:hover {{
    background: linear-gradient(120deg, {NAVY}, {TEAL_LIGHT}); color: #FFFFFF;
}}
.stButton button, .stDownloadButton button {{ border-radius: 10px; font-weight: 500; }}
[data-testid="stAlert"] {{ border-radius: 12px; }}

/* ---------- dropdowns in the main area: white box, teal border ----------
   Covers newer Streamlit (react-aria ComboBox) and older versions (baseweb select). */
[data-testid="stMain"] [data-testid="stSelectbox"] .react-aria-ComboBox > div,
[data-testid="stMain"] [data-testid="stMultiSelect"] .react-aria-ComboBox > div,
[data-testid="stMain"] [data-baseweb="select"] > div {{
    background: #FFFFFF !important;
    border: 1.5px solid #7FB8B2 !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(15, 118, 110, 0.12);
}}
[data-testid="stMain"] .react-aria-ComboBox > div:hover,
[data-testid="stMain"] [data-baseweb="select"] > div:hover {{ border-color: {TEAL} !important; }}
[data-testid="stMain"] .react-aria-ComboBox > div:focus-within,
[data-testid="stMain"] [data-baseweb="select"] > div:focus-within {{
    border-color: {TEAL} !important; box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.22);
}}
[data-testid="stMain"] [data-testid="stSelectbox"] input {{ color: {INK} !important; font-weight: 600; }}
[data-testid="stMain"] [data-testid="stSelectbox"] svg {{ color: {TEAL}; }}
[data-testid="stMain"] [data-testid="stWidgetLabel"] p {{ color: {NAVY}; font-weight: 600; }}
</style>
"""


def apply_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str, pills: list[str] | None = None) -> None:
    pill_html = "".join(f'<span class="rfp-pill">{html.escape(p)}</span>' for p in (pills or []))
    st.markdown(
        f'<div class="rfp-hero"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p>'
        f'{f"<div class=rfp-pills>{pill_html}</div>" if pill_html else ""}</div>',
        unsafe_allow_html=True,
    )
