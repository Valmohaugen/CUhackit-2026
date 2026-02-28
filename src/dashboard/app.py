"""Quantum DNS Shield — Streamlit Dashboard.

Main entry point. No sidebar — all controls are inline horizontal
dropdowns. Centered title, clean white background, tabbed panels.
"""
from __future__ import annotations

import streamlit as st

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path

ensure_project_root_on_path()

from src.dashboard.components.sidebar import render_control_bar
from src.dashboard.components.chatbot_panel import render_chat_tab

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

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #333333;
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
h3 {
    color: #333333 !important;
    font-weight: 600 !important;
    font-size: 1.15rem !important;
}

/* Top header bar */
.stApp > header {
    background: #FAFAFA !important;
    border-bottom: 3px solid #F56600;
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

/* Selectbox: compact */
.stSelectbox label {
    font-size: 0.8rem !important;
    color: #666666 !important;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.03em;
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

/* Hide anchors and status widget */
a[href^="#"], .stMarkdown a.header-link,
h1 a, h2 a, h3 a, h4 a, h5 a, h6 a,
[data-testid="stHeaderActionElements"],
[data-testid="stStatusWidget"] {
    display: none !important;
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
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Centered title
# ---------------------------------------------------------------------------

st.markdown(
    "<h1 style='text-align:center; margin-bottom:0;'>Quantum DNS Shield</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center; color:#666; margin-top:0.25rem; margin-bottom:1.5rem;'>"
    "Post-quantum DNS security · lattice-based cryptography · quantum random number generation"
    "</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Horizontal control bar (toggle dropdowns)
# ---------------------------------------------------------------------------

render_control_bar()

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
