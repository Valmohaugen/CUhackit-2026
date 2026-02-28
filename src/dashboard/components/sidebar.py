"""Inline control bar: horizontal toggle dropdowns.

Provides:
  - render_control_bar: Renders all toggles as compact horizontal dropdowns
    inside a sticky form
"""

from __future__ import annotations

import streamlit as st

from src.config.toggles import TOGGLES
from src.dashboard.utils import get_config, set_config


def render_control_bar() -> None:
    """Render horizontal toggle dropdowns inside a sticky form.

    Shows only the core operational toggles. Migration phase and deployment
    scenario are handled as presets in the HNDL Analysis panel (Attack Theater tab).
    """
    config = get_config()
    if config is None:
        st.error("Cannot connect to API")
        return

    # Only show core toggles — phase/scenario are moved to HNDL analysis as presets
    _CORE_TOGGLES = [k for k in TOGGLES if k not in ("phase", "scenario")]

    with st.form("control_form"):
        # Hidden marker for CSS :has() targeting
        st.markdown(
            '<span class="control-form-marker"></span>',
            unsafe_allow_html=True,
        )

        cols = st.columns(len(_CORE_TOGGLES) + 1)
        values = {}
        for col, name in zip(cols, _CORE_TOGGLES):
            toggle = TOGGLES[name]
            with col:
                current = config.get(name, toggle.default)
                idx = toggle.options.index(current) if current in toggle.options else 0
                values[name] = st.selectbox(
                    toggle.label,
                    options=toggle.options,
                    index=idx,
                    key=f"toggle_{name}",
                    help=toggle.description,
                )

        with cols[-1]:
            st.markdown("<br>", unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "Apply", type="primary", use_container_width=True,
            )

    if submitted:
        updates = {}
        for name in _CORE_TOGGLES:
            toggle = TOGGLES[name]
            current = config.get(name, toggle.default)
            if values[name] != current:
                updates[name] = values[name]
        if updates:
            set_config(updates)
        st.rerun()
