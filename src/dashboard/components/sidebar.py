"""Inline control bar: horizontal toggle dropdowns.

Provides:
  - render_control_bar: Renders all toggles as compact horizontal dropdowns
"""

from __future__ import annotations

import streamlit as st

from src.config.toggles import TOGGLES
from src.dashboard.utils import get_config, set_config


def render_control_bar() -> None:
    """Render horizontal toggle dropdowns in the main content area."""
    config = get_config()
    if config is None:
        st.error("Cannot connect to API")
        return

    cols = st.columns(len(TOGGLES))
    updates = {}
    for col, (name, toggle) in zip(cols, TOGGLES.items()):
        with col:
            current = config.get(name, toggle.default)
            idx = toggle.options.index(current) if current in toggle.options else 0
            new_val = st.selectbox(
                toggle.label,
                options=toggle.options,
                index=idx,
                key=f"toggle_{name}",
            )
            if new_val != current:
                updates[name] = new_val

    if updates:
        set_config(updates)
        st.rerun()
