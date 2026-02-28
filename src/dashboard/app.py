"""Quantum DNS Shield — Streamlit Dashboard.

Main entry point. No sidebar — all controls are inline horizontal
dropdowns. Centered title, clean white background, tabbed panels.
"""
from __future__ import annotations

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path()

import streamlit as st

from src.dashboard.components.sidebar import render_control_bar
from src.dashboard.components.chatbot_panel import render_chat_tab
from src.dashboard.utils import resolve_domain

st.set_page_config(
    page_title="Quantum DNS Shield",
    page_icon="shield",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Clean Modern Theme CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:wght@400&family=Inter:wght@300;400;500;600&display=swap');

/* Force ALL text black — overrides every Streamlit scoped style */
* {
    color: #111111 !important;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Exceptions: elements that legitimately need white text */
.stButton > button[kind="primary"],
.stButton > button[kind="primary"] *,
.stButton > button[kind="primary"] p,
.stProgress > div > div,
[data-testid="stNotificationContentSuccess"] *,
[data-testid="stNotificationContentError"] *,
[data-testid="stNotificationContentWarning"] * {
    color: #FFFFFF !important;
}

/* Hide sidebar completely */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
}

/* White / off-white background */
[data-testid="stAppViewContainer"] {
    background: #FAFAFA;
}
.stApp {
    background: #FAFAFA;
}

/* Headers */
h1 {
    font-family: 'DM Serif Display', Georgia, serif !important;
    color: #1a1a1a !important;
    font-weight: 400 !important;
    font-size: 2.25rem !important;
    letter-spacing: -0.02em;
}
h2 {
    color: #522D80 !important;
    font-weight: 600 !important;
    font-size: 1.5rem !important;
}
h3, h4, h5, h6 {
    color: #1a1a1a !important;
    font-weight: 600 !important;
}
h3 { font-size: 1.15rem !important; }

/* Hide top header bar entirely and collapse its space */
.stApp > header,
[data-testid="stHeader"] {
    display: none !important;
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* Remove top padding from main content area */
[data-testid="stAppViewBlockContainer"],
.block-container {
    padding-top: 0.25rem !important;
}
[data-testid="stMainBlockContainer"] {
    padding-top: 0.25rem !important;
}

/* Tabs */
button[data-baseweb="tab"] {
    color: #666666 !important;
    font-weight: 500;
    font-size: 0.95rem;
    border-bottom: 2px solid transparent;
    padding-bottom: 0.5rem;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #1a1a1a !important;
    border-bottom: 2px solid #F56600 !important;
    font-weight: 600;
}

/* Primary buttons: pill */
.stButton > button[kind="primary"] {
    background-color: #F56600 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 9999px !important;
    font-weight: 500;
    padding: 0.4rem 1.5rem;
    font-size: 0.9rem;
}
.stButton > button[kind="primary"]:hover {
    background-color: #D45500 !important;
}

/* Secondary buttons: pill outline */
.stButton > button[kind="secondary"],
.stButton > button:not([kind]) {
    border: 1px solid #D0D0D0 !important;
    color: #333333 !important;
    background: #FFFFFF !important;
    border-radius: 9999px !important;
    font-weight: 500;
    padding: 0.4rem 1.5rem;
    font-size: 0.9rem;
}
.stButton > button[kind="secondary"]:hover,
.stButton > button:not([kind]):hover {
    background: #F0F0F0 !important;
    border-color: #999999 !important;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E8E8E8;
    padding: 1rem;
    border-radius: 8px;
}
[data-testid="stMetricLabel"] {
    color: #888888 !important;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 500;
}
[data-testid="stMetricValue"] {
    color: #1a1a1a !important;
    font-weight: 600;
}

/* Selectbox: compact, centered labels */
.stSelectbox label {
    font-size: 0.8rem !important;
    color: #666666 !important;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    text-align: center !important;
    width: 100% !important;
    display: block !important;
}
/* Selectbox: cleaner dropdown bubble */
.stSelectbox [data-baseweb="select"] {
    border-radius: 8px !important;
    border: 1px solid #E0E0E0 !important;
}
.stSelectbox [data-baseweb="select"]:hover {
    border-color: #CCCCCC !important;
}
.stSelectbox [data-baseweb="select"] > div {
    text-align: center !important;
    justify-content: center !important;
    display: flex !important;
    align-items: center !important;
}
.stSelectbox [data-baseweb="select"] > div > div:first-child {
    flex: 1 !important;
    text-align: center !important;
    padding-right: 0 !important;
}
.stSelectbox [data-baseweb="select"] span,
.stSelectbox [data-baseweb="select"] [data-testid="stMarkdownContainer"] {
    text-align: center !important;
    width: 100% !important;
    display: block !important;
}
[data-baseweb="popover"] ul {
    border-radius: 8px !important;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08) !important;
    border: 1px solid #E8E8E8 !important;
}
[data-baseweb="popover"] li {
    text-align: center !important;
    justify-content: center !important;
}
[data-baseweb="popover"] li[aria-selected="true"] {
    background: #F56600 !important;
    color: #FFFFFF !important;
}

/* Progress bar */
.stProgress > div > div {
    background-color: #F56600 !important;
}

/* Links */
a { color: #F56600 !important; }
a:hover { color: #D45500 !important; }

/* Tables */
.stTable table { border-collapse: collapse; }
.stTable table th {
    background-color: #F5F5F5;
    color: #333333;
    font-weight: 600;
    padding: 0.6rem 0.75rem;
    border-bottom: 2px solid #E0E0E0;
}
.stTable table td {
    padding: 0.6rem 0.75rem;
    border-bottom: 1px solid #F0F0F0;
    color: #333333 !important;
}
[data-testid="stDataFrame"] thead th {
    background-color: #F5F5F5 !important;
    color: #333333 !important;
    font-weight: 600;
}

/* Dividers */
hr { border-color: #E8E8E8 !important; }

/* Hide anchors, status widget, and top toolbar (Deploy button) */
a[href^="#"], .stMarkdown a.header-link,
h1 a, h2 a, h3 a, h4 a, h5 a, h6 a,
[data-testid="stHeaderActionElements"],
[data-testid="stStatusWidget"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
    display: none !important;
}

/* Hide Streamlit developer toolbar */
[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],
.stDecoration {
    display: none !important;
}

/* Hide "Press Enter to submit form" instruction inside st.form */
[data-testid="InputInstructions"],
[data-testid="stFormSubmitButton"] p,
[data-testid="stFormSubmitButton"] small {
    display: none !important;
}

/* Sticky tier offsets */
:root {
    --sticky-global-controls-top: 0px;
    --sticky-resolver-top: 75px;
    --sticky-section-controls-top: 150px;
}

/* Sticky control bar form — pins settings to top on scroll */
[data-testid="stForm"]:has(.control-form-marker) {
    position: sticky;
    top: var(--sticky-global-controls-top);
    z-index: 1000;
    background: #FAFAFA;
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #E8E8E8;
}

/* Sticky resolver form — stacks below control bar */
[data-testid="stForm"]:has(.resolver-form-marker) {
    position: sticky;
    top: var(--sticky-resolver-top);
    z-index: 999;
    background: #FAFAFA;
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #E8E8E8;
}

/* Sticky per-section control rows — stack below global sticky forms */
[data-testid="stForm"]:has(.section-controls-form-marker) {
    position: sticky;
    top: var(--sticky-section-controls-top);
    z-index: 998;
    background: #FAFAFA;
    padding-top: 0.5rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #E8E8E8;
}
/* Expanders */
.streamlit-expanderHeader {
    color: #333333 !important;
    font-weight: 500;
}

/* Alerts — dark text on Streamlit's light-colored alert backgrounds */
.stAlert { border-radius: 8px; }
.stAlert p, .stAlert span,
.stAlert [data-testid="stMarkdownContainer"] p {
    color: #333333 !important;
}

/* Prevent charts from hijacking two-finger trackpad scroll.
   touch-action: pan-y lets the browser handle vertical scrolling natively
   instead of passing it to the Vega-Lite zoom/pan handler. */
[data-testid="stVegaLiteChart"],
[data-testid="stVegaLiteChart"] canvas,
[data-testid="stVegaLiteChart"] div,
[data-testid="stArrowVegaLiteChart"],
[data-testid="stArrowVegaLiteChart"] canvas,
[data-testid="stArrowVegaLiteChart"] div,
.stPlotlyChart,
.stPlotlyChart div,
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] div {
    touch-action: pan-y !important;
}
/* Block wheel-event zoom on chart canvases so scrolling passes through */
[data-testid="stVegaLiteChart"] canvas,
[data-testid="stArrowVegaLiteChart"] canvas {
    pointer-events: none !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Centered title
# ---------------------------------------------------------------------------

st.markdown(
    "<h1 style='text-align:center; margin-bottom:0;'>Quantum DNS Shield</h1>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Horizontal control bar (toggle dropdowns)
# ---------------------------------------------------------------------------

render_control_bar()

# ---------------------------------------------------------------------------
# Sticky domain search form (visible on all tabs)
# ---------------------------------------------------------------------------

with st.form("resolver_form"):
    st.markdown(
        '<span class="resolver-form-marker"></span>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns([3, 1])
    with col1:
        domain = st.text_input(
            "Domain to resolve",
            value=st.session_state.get("resolved_domain", "example.com"),
            placeholder="example.com",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        resolve_btn = st.form_submit_button(
            "Resolve", type="primary", use_container_width=True,
        )

if resolve_btn and domain:
    st.session_state["resolved_domain"] = domain
    with st.spinner("Resolving..."):
        result = resolve_domain(domain)
    if result:
        st.session_state["last_resolve_result"] = result
    else:
        st.error("Resolution failed. Check API connection.")

st.markdown("---")

# ---------------------------------------------------------------------------
# Tabbed panels
# ---------------------------------------------------------------------------

tab_resolver, tab_attack, tab_bench, tab_metrics, tab_chat = st.tabs([
    "DNS Resolver",
    "Attack Theater",
    "Benchmarks",
    "Live Metrics",
    "AI Chat",
])

with tab_resolver:
    from src.dashboard.components.resolver_panel import render_resolver_panel
    render_resolver_panel()

    st.markdown("---")
    from src.dashboard.components.scheme_overview_panel import render_scheme_overview
    render_scheme_overview()

    st.markdown("---")
    from src.dashboard.components.comparison_panel import render_comparison_panel
    render_comparison_panel()

with tab_attack:
    from src.dashboard.components.attack_panel import render_attack_panel
    render_attack_panel()

with tab_bench:
    from src.dashboard.components.benchmark_panel import render_benchmark_panel
    render_benchmark_panel()

with tab_metrics:
    from src.dashboard.components.metrics_panel import render_metrics_panel
    render_metrics_panel()

with tab_chat:
    render_chat_tab()

# Footer
st.markdown("---")
st.markdown(
    "<p style='text-align:center; color:#999; font-size:0.85rem;'>"
    "Quantum DNS Shield · CUhackit 2026 · Team Ransom · Clemson University"
    "</p>",
    unsafe_allow_html=True,
)
