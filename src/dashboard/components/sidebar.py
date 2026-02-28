"""Sidebar: Master toggle controls and QRNG status.

Provides:
  - render_sidebar: Renders all toggle dropdowns and QRNG pool gauge
"""

from __future__ import annotations

import streamlit as st

from src.config.toggles import TOGGLES
from src.dashboard.utils import get_config, get_qrng_status, set_config


def render_sidebar() -> None:
    """Render the sidebar with master toggles and QRNG status."""
    st.sidebar.title("Control Panel")

    # Load current config
    config = get_config()
    if config is None:
        st.sidebar.error("Cannot connect to API")
        return

    st.sidebar.markdown("---")
    st.sidebar.subheader("Master Toggles")

    updates = {}
    for name, toggle in TOGGLES.items():
        current = config.get(name, toggle.default)
        idx = toggle.options.index(current) if current in toggle.options else 0
        new_val = st.sidebar.selectbox(
            toggle.label,
            options=toggle.options,
            index=idx,
            help=toggle.description,
            key=f"toggle_{name}",
        )
        if new_val != current:
            updates[name] = new_val

    if updates:
        set_config(updates)
        st.sidebar.success("Config updated!")
        st.rerun()

    # QRNG Status
    st.sidebar.markdown("---")
    st.sidebar.subheader("QRNG Pool Status")

    status = get_qrng_status()
    if status:
        pool_size = status.get("pool_size", 0)
        max_pool = 50_000

        # Pool gauge
        pct = min(pool_size / max_pool, 1.0)
        st.sidebar.progress(pct, text=f"{pool_size:,} / {max_pool:,} seeds")

        col1, col2 = st.sidebar.columns(2)
        col1.metric("Backend", status.get("last_backend", "none"))
        col2.metric("Qubits", status.get("last_qubits", "0"))

        st.sidebar.caption(f"Last fill: {status.get('last_fill', 'never')}")
        st.sidebar.caption(f"Entropy: {status.get('last_entropy', '0.0')}")
    else:
        st.sidebar.warning("QRNG status unavailable")
