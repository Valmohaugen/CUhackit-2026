"""Quantum DNS Shield — Streamlit Dashboard.

Main entry point for the Streamlit frontend. Renders the sidebar
and tab layout for all module panels.
"""
from __future__ import annotations
from pathlib import Path
from src.dashboard.components.sidebar import render_sidebar

import sys
import streamlit as st

try:
    from ._bootstrap import ensure_project_root_on_path
except ImportError:
    from _bootstrap import ensure_project_root_on_path


def ensure_project_root_on_path() -> None:
    """Insert project root at the start of sys.path if not already present."""
    project_root = Path(__file__).resolve().parents[2]  # adjust as needed
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

ensure_project_root_on_path()

st.set_page_config(
    page_title="Quantum DNS Shield",
    page_icon="shield",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar (master toggles + QRNG status)
# ---------------------------------------------------------------------------

render_sidebar()

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title("Quantum DNS Shield")
st.markdown(
    "Post-quantum DNS security powered by **lattice-based cryptography** "
    "and **quantum random number generation**."
)

# Tab layout for all module panels
tab_resolver, tab_attack, tab_bench, tab_migration, tab_metrics = st.tabs([
    "DNS Resolver",
    "Attack Theater",
    "Benchmarks",
    "Migration Matrix",
    "Live Metrics",
])

with tab_resolver:
    from src.dashboard.components.resolver_panel import render_resolver_panel
    render_resolver_panel()

with tab_attack:
    from src.dashboard.components.attack_panel import render_attack_panel
    render_attack_panel()

with tab_bench:
    from src.dashboard.components.benchmark_panel import render_benchmark_panel
    render_benchmark_panel()

with tab_migration:
    from src.dashboard.components.migration_panel import render_migration_panel
    render_migration_panel()

with tab_metrics:
    from src.dashboard.components.metrics_panel import render_metrics_panel
    render_metrics_panel()

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption(
    "Quantum DNS Shield | CUhackit 2026 | Team Ransom | "
    "Clemson University Quantum Group"
)
